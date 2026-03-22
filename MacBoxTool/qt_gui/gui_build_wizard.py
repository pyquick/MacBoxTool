"""
gui_build_wizard.py: EFI build wizard with hardware validation
"""

from ..include import *
from ..UIkit.components.dialog_box import MessageBox, MessageBoxBase
from ..datasets.smbios_data import smbios_dictionary
from ..datasets import cpu_data, os_data


# SMBIOS models suitable for Hackintosh (Haswell+ with reasonable Max OS)
HACKINTOSH_SMBIOS_CATEGORIES = {
    "iMac (Desktop with iGPU)": [
        "iMac14,1", "iMac14,2", "iMac14,3", "iMac14,4",
        "iMac15,1", "iMac16,1", "iMac16,2",
        "iMac17,1", "iMac18,1", "iMac18,2", "iMac18,3",
        "iMac19,1", "iMac19,2", "iMac20,1", "iMac20,2",
    ],
    "iMac Pro / Mac Pro (Desktop without iGPU)": [
        "iMacPro1,1", "MacPro7,1",
    ],
    "MacBook Pro (Laptop)": [
        "MacBookPro11,1", "MacBookPro11,2", "MacBookPro11,3",
        "MacBookPro11,4", "MacBookPro11,5",
        "MacBookPro12,1",
        "MacBookPro13,1", "MacBookPro13,2", "MacBookPro13,3",
        "MacBookPro14,1", "MacBookPro14,2", "MacBookPro14,3",
        "MacBookPro15,1", "MacBookPro15,2", "MacBookPro15,3", "MacBookPro15,4",
        "MacBookPro16,1", "MacBookPro16,2", "MacBookPro16,3", "MacBookPro16,4",
    ],
    "MacBook Air (Laptop)": [
        "MacBookAir6,1", "MacBookAir6,2",
        "MacBookAir7,1", "MacBookAir7,2",
        "MacBookAir8,1", "MacBookAir8,2",
        "MacBookAir9,1",
    ],
}


def _get_smbios_display_text(model: str) -> str:
    """Format SMBIOS model for display in ComboBox"""
    info = smbios_dictionary.get(model, {})
    name = info.get("Marketing Name", "")
    cpu_gen = info.get("CPU Generation", 0)
    max_os = info.get("Max OS Supported", 0)

    # Map CPU generation int to readable name
    gen_names = {v.value: v.name.replace("_", " ").title() for v in cpu_data.CPUGen}
    gen_str = gen_names.get(cpu_gen, f"Gen {cpu_gen}")

    # Map max OS int to readable name
    os_names = {v.value: v.name.replace("_", " ").title() for v in os_data.os_data}
    os_str = os_names.get(max_os, f"macOS {max_os}")
    if max_os == 99:
        os_str = "Latest"

    if name:
        return f"{model}  —  {name}  |  {gen_str}  |  Max: {os_str}"
    return f"{model}  |  {gen_str}  |  Max: {os_str}"


class SMBIOSSelectDialog(MessageBoxBase):
    """Dialog for selecting SMBIOS model with category filter and ComboBox"""

    def __init__(self, recommended: str, explanation: str, parent=None):
        super().__init__(parent=parent)
        self.recommended = recommended
        self.selected_model = recommended

        self.widget.setMinimumWidth(550)

        # Title
        title = SubtitleLabel("Select SMBIOS Model")
        self.viewLayout.addWidget(title)

        # Recommendation info
        info_label = BodyLabel(explanation)
        info_label.setWordWrap(True)
        self.viewLayout.addWidget(info_label)

        # Category selector
        cat_row = QHBoxLayout()
        cat_row.addWidget(StrongBodyLabel("Category:"))
        self.category_combo = ComboBox()
        for cat in HACKINTOSH_SMBIOS_CATEGORIES:
            self.category_combo.addItem(cat)
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        cat_row.addWidget(self.category_combo, 1)
        self.viewLayout.addLayout(cat_row)

        # Model selector
        model_row = QHBoxLayout()
        model_row.addWidget(StrongBodyLabel("SMBIOS:"))
        self.model_combo = ComboBox()
        self.model_combo.setMinimumWidth(400)
        model_row.addWidget(self.model_combo, 1)
        self.viewLayout.addLayout(model_row)

        # Model detail card
        self.detail_label = BodyLabel("")
        self.detail_label.setWordWrap(True)
        self.viewLayout.addWidget(self.detail_label)

        self.model_combo.currentIndexChanged.connect(self._on_model_changed)

        # Set initial category based on recommended model
        self._set_initial_category(recommended)

        self.yesButton.setText("Use Selected")
        self.cancelButton.setText("Cancel")

    def _set_initial_category(self, model: str):
        """Find and set the category containing the recommended model"""
        for cat, models in HACKINTOSH_SMBIOS_CATEGORIES.items():
            if model in models:
                self.category_combo.setCurrentText(cat)
                self._on_category_changed(cat)
                # Select the recommended model
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) == model:
                        self.model_combo.setCurrentIndex(i)
                        break
                return
        # Fallback: select first category
        first_cat = list(HACKINTOSH_SMBIOS_CATEGORIES.keys())[0]
        self.category_combo.setCurrentText(first_cat)
        self._on_category_changed(first_cat)

    def _on_category_changed(self, category: str):
        """Populate model ComboBox based on selected category"""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        models = HACKINTOSH_SMBIOS_CATEGORIES.get(category, [])
        for model in models:
            if model in smbios_dictionary:
                display = _get_smbios_display_text(model)
                self.model_combo.addItem(display)
                # Store model ID in item data
                self.model_combo.setItemData(self.model_combo.count() - 1, model)
        self.model_combo.blockSignals(False)

        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)
            self._on_model_changed(0)

    def _on_model_changed(self, index: int):
        """Update detail info when model selection changes"""
        if index < 0:
            return
        model = self.model_combo.itemData(index)
        if not model:
            return
        self.selected_model = model
        info = smbios_dictionary.get(model, {})

        details = []
        if "Marketing Name" in info:
            details.append(f"Name: {info['Marketing Name']}")
        if "Board ID" in info:
            details.append(f"Board ID: {info['Board ID']}")
        if "SecureBootModel" in info:
            sb = info["SecureBootModel"]
            details.append(f"Secure Boot: {sb if sb else 'None'}")

        max_os = info.get("Max OS Supported", 0)
        os_names = {v.value: v.name.replace("_", " ").title() for v in os_data.os_data}
        os_str = os_names.get(max_os, f"macOS {max_os}")
        if max_os == 99:
            os_str = "Latest (no limit)"
        details.append(f"Max macOS: {os_str}")

        if model == self.recommended:
            details.append("(Recommended for your hardware)")

        self.detail_label.setText("\n".join(details))


class BuildWizard:
    """Wizard for guided EFI building with validation"""

    def __init__(self, constants, parent=None):
        self.constants = constants
        self.parent = parent
        self.target_macos = 13  # Default to macOS 13

    def run(self) -> tuple[bool, str]:
        """
        Run the build wizard

        Returns:
            (success, smbios_model): Tuple of success status and selected SMBIOS
        """
        # Step 1: Validate hardware
        if not self._validate_hardware():
            return False, None, None

        # Step 2: Select SMBIOS
        smbios_model = self._select_smbios()
        if not smbios_model:
            return False, None, None

        # Step 3: Confirm build
        if not self._confirm_build(smbios_model):
            return False, None, None

        return True, smbios_model, self.target_macos

    def _validate_hardware(self) -> bool:
        """Validate hardware and show results"""
        from ..validation import validate_cpu, validate_gpu, validate_storage, validate_network

        issues = []
        has_critical = False

        # CPU validation (blocking)
        is_supported, msg = validate_cpu(self.constants, self.target_macos)
        if not is_supported:
            has_critical = True
            issues.append(("CRITICAL", msg))
        elif msg:
            issues.append(("WARNING", msg))

        # GPU validation (warning)
        has_warning, msg = validate_gpu(self.constants)
        if has_warning:
            issues.append(("WARNING", msg))

        # Storage validation (warning)
        has_warning, msg = validate_storage(self.constants)
        if has_warning:
            issues.append(("WARNING", msg))

        # Network info
        has_info, msg = validate_network(self.constants)
        if has_info:
            issues.append(("INFO", msg))

        if not issues:
            return True

        # Build message
        result_msg = "Hardware Validation Results:\n\n"
        for severity, issue_msg in issues:
            if severity == "CRITICAL":
                result_msg += f"[CRITICAL] {issue_msg}\n\n"
            elif severity == "WARNING":
                result_msg += f"[WARNING] {issue_msg}\n\n"
            else:
                result_msg += f"[INFO] {issue_msg}\n\n"

        if has_critical:
            box = MessageBox("Unsupported Hardware", result_msg, self.parent)
            box.cancelButton.hide()
            box.exec()
            return False
        else:
            box = MessageBox("Hardware Warnings", result_msg + "Continue anyway?", self.parent)
            return box.exec()

    def _select_smbios(self) -> str:
        """Select SMBIOS model via dialog with ComboBox"""
        from ..efi_hack.builder import _detect_cpu_gen, _is_laptop

        # Auto-detect recommended SMBIOS
        recommended = self._auto_select_smbios()
        explanation = self._explain_smbios(recommended)

        # Show selection dialog
        dialog = SMBIOSSelectDialog(recommended, explanation, self.parent)
        if dialog.exec():
            return dialog.selected_model

        return None

    def _auto_select_smbios(self) -> str:
        """Auto-select SMBIOS based on hardware"""
        from ..efi_hack.builder import _detect_cpu_gen, _is_laptop

        if not self.constants.computer or not self.constants.computer.cpu:
            return "iMac19,1"

        cpu_gen = _detect_cpu_gen(self.constants.computer.cpu.name)
        has_igpu = self.constants.computer.igpu is not None
        is_laptop = _is_laptop(self.constants.computer)

        if is_laptop:
            laptop_map = {
                "ivy_bridge": "MacBookPro10,1",
                "haswell": "MacBookPro11,1",
                "broadwell": "MacBookPro12,1",
                "skylake": "MacBookPro13,1",
                "kaby_lake": "MacBookPro14,1",
                "coffee_lake": "MacBookPro15,1",
                "comet_lake": "MacBookPro16,1",
            }
            return laptop_map.get(cpu_gen, "MacBookPro15,1")

        if not has_igpu:
            return "iMacPro1,1"

        desktop_map = {
            "ivy_bridge": "iMac13,1",
            "haswell": "iMac15,1",
            "broadwell": "iMac16,1",
            "skylake": "iMac17,1",
            "kaby_lake": "iMac18,2",
            "coffee_lake": "iMac19,1",
            "comet_lake": "iMac20,1",
        }
        return desktop_map.get(cpu_gen, "iMac19,1")

    def _explain_smbios(self, smbios_model: str) -> str:
        """Generate explanation for recommended SMBIOS"""
        from ..efi_hack.builder import _detect_cpu_gen, _is_laptop

        info = smbios_dictionary.get(smbios_model, {})
        if not info:
            return f"Selected {smbios_model} (default)"

        cpu_gen = _detect_cpu_gen(self.constants.computer.cpu.name) if self.constants.computer and self.constants.computer.cpu else "unknown"
        has_igpu = self.constants.computer.igpu is not None if self.constants.computer else False
        is_laptop = _is_laptop(self.constants.computer) if self.constants.computer else False

        explanation = f"Recommended: {smbios_model}\n"
        if is_laptop:
            explanation += f"Reason: Laptop with {cpu_gen.replace('_', ' ').title()} CPU"
        elif not has_igpu:
            explanation += f"Reason: Desktop without iGPU"
        else:
            explanation += f"Reason: Desktop with {cpu_gen.replace('_', ' ').title()} CPU and iGPU"

        return explanation

    def _confirm_build(self, smbios_model: str) -> bool:
        """Confirm build with selected SMBIOS info"""
        info = smbios_dictionary.get(smbios_model, {})
        name = info.get("Marketing Name", smbios_model)

        msg = (
            f"SMBIOS: {smbios_model}\n"
            f"({name})\n\n"
            f"Ready to build OpenCore EFI.\nProceed?"
        )
        box = MessageBox("Confirm Build", msg, self.parent)
        return box.exec()
