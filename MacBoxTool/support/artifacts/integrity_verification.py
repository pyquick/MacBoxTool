"""
integrity_verification.py: macOS installer chunklist verification
Validates downloaded InstallAssistant.pkg against Apple's integrity data (CNKL format)
"""

import hashlib
import logging
import struct
from enum import Enum
from pathlib import Path
from typing import Optional, BinaryIO, Dict, Callable
from io import BytesIO


class ChunklistStatus(Enum):
    """Status of chunklist verification"""
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"


class ChunklistVerification:
    """
    Verifies macOS installer integrity using Apple's CNKL binary chunklist format

    CNKL binary format:
    - Header: 36 bytes (magic, header size, version/methods, offsets)
    - Entries: chunk_count entries of 36 bytes each:
        - uint32 LE: chunk size
        - bytes[32]: SHA-256 hash of chunk data
    - Signature: method-dependent data at the header's signature offset
    """

    CHUNKLIST_MAGIC = b'CNKL'
    HEADER_FORMAT = '<4sIBBBxQQQ'
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    ENTRY_SIZE = 36  # 4 bytes size + 32 bytes SHA-256
    CHUNK_METHOD_SHA256 = 1
    SIGNATURE_METHOD_RSA = 1
    SIGNATURE_METHOD_SHA256 = 2

    def __init__(self, pkg_path: Path, chunklist_stream: BytesIO):
        self.pkg_path = pkg_path
        self.chunklist_stream = chunklist_stream
        self.status = ChunklistStatus.IN_PROGRESS
        self.current_chunk = 0
        self.total_chunks = 0
        self.chunks: Dict[int, Dict[str, object]] = {}
        self._progress_callback: Optional[Callable[[int, int], None]] = None
        self._parsed = False

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set a callback for progress updates during validation"""
        self._progress_callback = callback

    def parse(self) -> bool:
        """
        Parse the chunklist to populate chunk entries.
        Separate from validate() so callers can inspect total_chunks
        before starting verification.

        Returns:
            True if parsing successful, False otherwise
        """
        if self._parsed:
            return True
        if not self._parse_chunklist():
            self.status = ChunklistStatus.FAILURE
            return False
        return True

    def verify(self) -> bool:
        """
        Verify chunks against the parsed chunklist.
        Requires parse() to have been called first.
        Emits progress via callback if set.

        Returns:
            True if all chunks verified, False otherwise
        """
        if not self._verify_chunks():
            self.status = ChunklistStatus.FAILURE
            return False
        self.status = ChunklistStatus.SUCCESS
        return True

    def validate(self) -> None:
        """
        Start validation process (parse + verify).
        Sets self.status to SUCCESS or FAILURE when complete.
        Updates self.current_chunk during progress.
        """
        try:
            if not self.parse():
                return

            self.verify()

        except Exception as e:
            logging.error(f"Chunklist verification error: {e}")
            self.status = ChunklistStatus.FAILURE

    def _parse_chunklist(self) -> bool:
        """
        Parse Apple's binary CNKL chunklist format

        Returns:
            True if parsing successful, False otherwise
        """
        try:
            content = self.chunklist_stream.read()

            # Validate magic
            if len(content) < self.HEADER_SIZE:
                logging.error(f"Chunklist too small: {len(content)} bytes")
                return False

            if content[:4] != self.CHUNKLIST_MAGIC:
                logging.error(f"Invalid chunklist magic: {content[:4]!r}")
                return False

            # Parse the fixed CNKL v1 header. Counts and offsets are uint64.
            (
                magic,
                header_size,
                file_version,
                chunk_method,
                signature_method,
                chunk_count,
                chunk_offset,
                signature_offset,
            ) = struct.unpack_from(self.HEADER_FORMAT, content, 0)

            if header_size < self.HEADER_SIZE or header_size > len(content):
                logging.error(f"Invalid chunklist header size: {header_size}")
                return False
            if file_version != 1:
                logging.error(f"Unsupported chunklist version: {file_version}")
                return False
            if chunk_method != self.CHUNK_METHOD_SHA256:
                logging.error(f"Unsupported chunk hash method: {chunk_method}")
                return False
            if chunk_offset < header_size:
                logging.error(f"Invalid chunk data offset: {chunk_offset}")
                return False

            self.total_chunks = chunk_count
            logging.info(
                f"Chunklist: magic={magic!r}, header_size={header_size}, "
                f"version={file_version}, chunk_method={chunk_method}, "
                f"signature_method={signature_method}, chunk_count={self.total_chunks}"
            )

            entries_start = chunk_offset
            entries_end = entries_start + self.total_chunks * self.ENTRY_SIZE

            if entries_end > len(content) or signature_offset < entries_end:
                logging.error(
                    f"Invalid chunklist offsets: entries end at {entries_end}, "
                    f"signature starts at {signature_offset}, file size is {len(content)}"
                )
                return False

            for i in range(self.total_chunks):
                entry_offset = entries_start + i * self.ENTRY_SIZE
                chunk_size = struct.unpack_from('<I', content, entry_offset)[0]
                chunk_hash = content[entry_offset + 4:entry_offset + self.ENTRY_SIZE]

                if chunk_size == 0:
                    logging.error(f"Invalid zero-sized chunk at index {i}")
                    return False

                self.chunks[i] = {
                    'size': chunk_size,
                    'checksum': chunk_hash.hex()
                }

            signature = content[signature_offset:]
            if signature_method == self.SIGNATURE_METHOD_SHA256:
                if len(signature) != hashlib.sha256().digest_size:
                    logging.error(f"Invalid SHA-256 signature size: {len(signature)}")
                    return False
                if hashlib.sha256(content[:signature_offset]).digest() != signature:
                    logging.error("Chunklist SHA-256 signature mismatch")
                    return False
            elif signature_method == self.SIGNATURE_METHOD_RSA:
                if not signature:
                    logging.error("Chunklist RSA signature is missing")
                    return False
            else:
                logging.error(f"Unsupported chunklist signature method: {signature_method}")
                return False

            self._parsed = True
            logging.info(f"Parsed {len(self.chunks)} chunk entries")
            return True

        except Exception as e:
            logging.error(f"Error parsing chunklist: {e}")
            return False

    def _verify_chunks(self) -> bool:
        """
        Verify each chunk's SHA-256 checksum against the chunklist

        Returns:
            True if all chunks valid, False otherwise
        """
        try:
            if not self.pkg_path.exists():
                logging.error(f"Installer file not found: {self.pkg_path}")
                return False

            pkg_size = self.pkg_path.stat().st_size
            expected_total = sum(c['size'] for c in self.chunks.values())
            logging.info(f"PKG size: {pkg_size}, expected from chunks: {expected_total}")
            if pkg_size != expected_total:
                logging.error(
                    f"Installer size mismatch: expected {expected_total}, got {pkg_size}"
                )
                return False

            with open(self.pkg_path, 'rb') as f:
                for chunk_num in range(self.total_chunks):
                    if chunk_num not in self.chunks:
                        logging.warning(f"Chunk {chunk_num} not in chunklist, skipping")
                        continue

                    self.current_chunk = chunk_num + 1
                    expected_size = self.chunks[chunk_num]['size']
                    expected_checksum = self.chunks[chunk_num]['checksum']

                    # Read chunk data
                    chunk_data = f.read(expected_size)

                    if not chunk_data:
                        logging.error(f"Reached end of file at chunk {chunk_num + 1}")
                        return False

                    if len(chunk_data) != expected_size:
                        logging.error(f"Chunk {chunk_num} size mismatch: "
                                       f"expected {expected_size}, got {len(chunk_data)}")
                        return False

                    # Verify checksum
                    actual_checksum = hashlib.sha256(chunk_data).hexdigest()

                    if actual_checksum != expected_checksum:
                        logging.error(f"Chunk {chunk_num + 1}: checksum mismatch")
                        logging.error(f"  Expected: {expected_checksum}")
                        logging.error(f"  Actual:   {actual_checksum}")
                        return False

                    # Emit progress via callback
                    if self._progress_callback:
                        self._progress_callback(self.current_chunk, self.total_chunks)
                        if self.status == ChunklistStatus.FAILURE:
                            return False

            logging.info(f"All {self.total_chunks} chunks verified successfully")
            return True

        except Exception as e:
            logging.error(f"Error verifying chunks: {e}")
            return False

    def get_progress_percentage(self) -> int:
        """
        Get validation progress as percentage

        Returns:
            Progress percentage (0-100)
        """
        if self.total_chunks == 0:
            return 0
        return int((self.current_chunk / self.total_chunks) * 100)
