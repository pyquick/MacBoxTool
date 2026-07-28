"""
products.py: Parse products from Software Update Catalog
"""

import re
import plistlib

import packaging.version
import xml.etree.ElementTree as ET

from pathlib   import Path
from urllib.parse import urlparse
from functools import cached_property
from concurrent.futures import ThreadPoolExecutor, as_completed

from .url       import CatalogURL
from .constants import CatalogVersion, SeedType

from ..support import network_handler


class CatalogProducts:
    """
    Args:
        catalog                       (dict): Software Update Catalog (contents of CatalogURL's URL)
        install_assistants_only       (bool): Only list InstallAssistant products
        only_vmm_install_assistants   (bool): Only list VMM-x86_64-compatible InstallAssistant products
        max_install_assistant_version (CatalogVersion): Maximum InstallAssistant version to list
    """

    LEGACY_INSTALL_ASSISTANT_PACKAGE = "InstallAssistantAuto.pkg"
    LEGACY_INSTALL_ESD_PACKAGE = "InstallESDDmg.pkg"
    LEGACY_REQUIRED_COMPONENTS = (
        LEGACY_INSTALL_ASSISTANT_PACKAGE,
        LEGACY_INSTALL_ESD_PACKAGE,
        "BaseSystem.dmg",
        "BaseSystem.chunklist",
        "AppleDiagnostics.dmg",
        "AppleDiagnostics.chunklist",
    )
    INSTALL_ASSISTANT_VERSION_MAP = {
        CatalogVersion.MOUNTAIN_LION: "10.8",
        CatalogVersion.LION: "10.7",
        CatalogVersion.SNOW_LEOPARD: "10.6",
        CatalogVersion.LEOPARD: "10.5",
        CatalogVersion.TIGER: "10.4",
    }
    OFFICIAL_LEGACY_INSTALLERS = [
        {
            "ProductID": "061-39476",
            "PostDate": "2019-10-24 03:19:02",
            "Title": "macOS Sierra",
            "Build": "16G29",
            "Version": "10.12.6",
            "URL": "http://updates-http.cdn-apple.com/2019/cert/061-39476-20191023-48f365f4-0015-4c41-9f44-39d3d2aca067/InstallOS.dmg",
            "Size": 5007882126,
            "XNUMajor": 16,
        },
        {
            "ProductID": "061-41424",
            "PostDate": "2019-10-24 18:19:26",
            "Title": "OS X El Capitan",
            "Build": "15G31",
            "Version": "10.11.6",
            "URL": "http://updates-http.cdn-apple.com/2019/cert/061-41424-20191024-218af9ec-cf50-4516-9011-228c78eda3d2/InstallMacOSX.dmg",
            "Size": 6204629298,
            "XNUMajor": 15,
        },
        {
            "ProductID": "061-41343",
            "PostDate": "2019-10-24 03:09:04",
            "Title": "OS X Yosemite",
            "Build": "14F27",
            "Version": "10.10.5",
            "URL": "http://updates-http.cdn-apple.com/2019/cert/061-41343-20191023-02465f92-3ab5-4c92-bfe2-b725447a070d/InstallMacOSX.dmg",
            "Size": 5718074248,
            "XNUMajor": 14,
        },
        {
            "ProductID": "031-0627",
            "PostDate": "2021-06-15 03:55:42",
            "Title": "OS X Mountain Lion",
            "Build": "12F45",
            "Version": "10.8.5",
            "URL": "https://updates.cdn-apple.com/2021/macos/031-0627-20210614-90D11F33-1A65-42DD-BBEA-E1D9F43A6B3F/InstallMacOSX.dmg",
            "Size": 4449317520,
            "XNUMajor": 12,
        },
        {
            "ProductID": "041-7683",
            "PostDate": "2021-06-15 04:01:21",
            "Title": "Mac OS X Lion",
            "Build": "11G63",
            "Version": "10.7.5",
            "URL": "https://updates.cdn-apple.com/2021/macos/041-7683-20210614-E610947E-C7CE-46EB-8860-D26D71F0D3EA/InstallMacOSX.dmg",
            "Size": 4720237409,
            "XNUMajor": 11,
        },
    ]

    def __init__(self,
                 catalog: dict,
                 install_assistants_only: bool = True,
                 only_vmm_install_assistants: bool = True,
                 max_install_assistant_version: CatalogVersion = CatalogVersion.GOLDEN_GATE
                ) -> None:
        self.catalog:             dict = catalog
        self.ia_only:             bool = install_assistants_only
        self.vmm_only:            bool = only_vmm_install_assistants
        max_version = self.INSTALL_ASSISTANT_VERSION_MAP.get(max_install_assistant_version, max_install_assistant_version.value)
        self.max_ia_version: packaging = packaging.version.parse(f"{max_version}.99.99")
        self.max_ia_catalog: CatalogVersion = max_install_assistant_version


    @staticmethod
    def _package_name(url: str) -> str:
        return Path(urlparse(url).path).name

    def _legacy_parse_info_plist(self, data: dict) -> dict:
        """
        Legacy version of parsing for installer details through Info.plist
        """

        if "MobileAssetProperties" not in data:
            return {}
        if "SupportedDeviceModels" not in data["MobileAssetProperties"]:
            return {}
        if "OSVersion" not in data["MobileAssetProperties"]:
            return {}
        if "Build" not in data["MobileAssetProperties"]:
            return {}

        # Ensure Apple Silicon specific Installers are not listed
        #if "VMM-x86_64" not in data["MobileAssetProperties"]["SupportedDeviceModels"]:
         #   if self.vmm_only:
          #      return {"Missing VMM Support": True}

        version = data["MobileAssetProperties"]["OSVersion"]
        build   = data["MobileAssetProperties"]["Build"]

        catalog = ""
        try:
            catalog = data["MobileAssetProperties"]["BridgeVersionInfo"]["CatalogURL"]
        except KeyError:
            pass

        if any([version, build]) is None:
            return {}

        return {
            "Version": version,
            "Build":   build,
            "Catalog": CatalogURL().catalog_url_to_seed(catalog),
        }


    def _parse_mobile_asset_plist(self, data: dict) -> dict:
        """
        Parses the MobileAsset plist for installer details

        With macOS Sequoia, the Info.plist is no longer present in the InstallAssistant's assets
        """
        _does_support_vmm = False
        for entry in data["Assets"]:
            if "SupportedDeviceModels" not in entry:
                continue
            if "OSVersion" not in entry:
                continue
            if "Build" not in entry:
                continue
            #if "VMM-x86_64" not in entry["SupportedDeviceModels"]:
             #   if self.vmm_only:
              #      continue

            _does_support_vmm = True

            build   = entry["Build"]
            version = entry["OSVersion"]

            catalog_url = ""
            try:
                catalog_url = entry["BridgeVersionInfo"]["CatalogURL"]
            except KeyError:
                pass

            return {
                "Version": version,
                "Build":   build,
                "Catalog": CatalogURL().catalog_url_to_seed(catalog_url),
            }

        if _does_support_vmm is False:
            if self.vmm_only:
                return {"Missing VMM Support": True}

        return {}


    def _parse_english_distributions(self, data: bytes) -> dict:
        """
        Resolve Title, Build and Version from the English distribution file
        """
        try:
            plist_contents = plistlib.loads(data)
        except plistlib.InvalidFileException:
            plist_contents = None

        try:
            xml_contents = ET.fromstring(data)
        except ET.ParseError:
            xml_contents = None

        _product_map = {
            "Title":   None,
            "Build":   None,
            "Version": None,
        }

        if plist_contents:
            if "macOSProductBuildVersion" in plist_contents:
                _product_map["Build"] = plist_contents["macOSProductBuildVersion"]
            if "macOSProductVersion" in plist_contents:
                _product_map["Version"] = plist_contents["macOSProductVersion"]
            if "BUILD" in plist_contents:
                _product_map["Build"] = plist_contents["BUILD"]
            if "VERSION" in plist_contents:
                _product_map["Version"] = plist_contents["VERSION"]

        if xml_contents:
            # Fetch item title
            item_title = xml_contents.find(".//title").text
            if item_title in ["SU_TITLE", "MANUAL_TITLE", "MAN_TITLE"]:
                # regex search the contents for the title
                title_search = re.search(r'"SU_TITLE"\s*=\s*"(.*)";', data.decode("utf-8"))
                if title_search:
                    item_title = title_search.group(1)

            _product_map["Title"] = item_title

        return _product_map


    def _build_installer_name(self, version: str, catalog: SeedType) -> str:
        """
        Builds the installer name based on the version and catalog
        """
        try:
            marketing_name = CatalogVersion(version.split(".")[0]).name
        except ValueError:
            marketing_name = "Unknown"

        # Replace _ with space
        marketing_name = marketing_name.replace("_", " ")

        # Convert to upper for each word
        marketing_name = "macOS " + " ".join([word.capitalize() for word in marketing_name.split()])

        # Append Beta if needed
        if catalog in [SeedType.DeveloperSeed, SeedType.PublicSeed, SeedType.CustomerSeed]:
            marketing_name += " Beta"

        return marketing_name


    def _list_latest_installers_only(self, products: list) -> list:
        """Return the newest installer for each of the four latest macOS families."""
        supported_versions = []
        did_find_latest = False
        for version in CatalogVersion:
            if not did_find_latest:
                if version != self.max_ia_catalog:
                    continue
                did_find_latest = True

            supported_versions.append(version)
            if len(supported_versions) == 4:
                break

        latest_by_family = {}
        for installer in products:
            installer_version = installer.get("Version")
            if not installer_version:
                continue

            family = next(
                (
                    version for version in supported_versions
                    if installer_version == version.value or installer_version.startswith(f"{version.value}.")
                ),
                None,
            )
            if family is None:
                continue

            try:
                version_key = packaging.version.parse(installer_version)
            except packaging.version.InvalidVersion:
                continue

            current = latest_by_family.get(family)
            if current is None:
                latest_by_family[family] = installer
                continue

            current_key = self._version_sort_key(current.get("Version", ""))
            if version_key > current_key or (
                version_key == current_key
                and installer.get("PostDate", "") > current.get("PostDate", "")
            ):
                latest_by_family[family] = installer

        return [
            latest_by_family[version]
            for version in supported_versions
            if version in latest_by_family
        ]


    def _official_legacy_products(self, products: list) -> list:
        existing_versions = {product.get("Version") for product in products}
        legacy_products = []

        for installer in self.OFFICIAL_LEGACY_INSTALLERS:
            version = installer["Version"]
            if version in existing_versions:
                continue
            try:
                if packaging.version.parse(version) > self.max_ia_version:
                    continue
            except packaging.version.InvalidVersion:
                continue

            legacy_products.append({
                "ProductID": installer["ProductID"],
                "PostDate": installer["PostDate"],
                "Title": installer["Title"],
                "Build": installer["Build"],
                "Version": version,
                "Catalog": SeedType.PublicRelease,
                "InstallAssistant": {
                    "URL": installer["URL"],
                    "Size": installer["Size"],
                    "XNUMajor": installer["XNUMajor"],
                    "LegacyInstaller": True,
                    "DirectDownload": True,
                    "Packages": [
                        {
                            "URL": installer["URL"],
                            "Size": installer["Size"],
                            "IntegrityDataURL": None,
                            "IntegrityDataSize": 0,
                        }
                    ],
                },
            })

        return legacy_products


    def _version_sort_key(self, version: str):
        try:
            return packaging.version.parse(version)
        except packaging.version.InvalidVersion:
            return packaging.version.parse("0.0.0")


    def _fetch_catalog_metadata(self, products: dict) -> dict:
        metadata_urls = set()
        for product in products.values():
            packages = product.get("Packages", [])
            package_names = {self._package_name(package.get("URL", "")) for package in packages}
            is_installer = (
                "InstallAssistant.pkg" in package_names
                or self.LEGACY_INSTALL_ASSISTANT_PACKAGE in package_names
                or self.LEGACY_INSTALL_ESD_PACKAGE in package_names
            )
            if not is_installer:
                continue

            for package in packages:
                package_url = package.get("URL")
                if package_url and self._package_name(package_url) in {
                    "Info.plist",
                    "com_apple_MobileAsset_MacSoftwareUpdate.plist",
                }:
                    metadata_urls.add(package_url)

            distributions = product.get("Distributions", {})
            distribution_url = distributions.get("English") or distributions.get("en")
            if distribution_url:
                metadata_urls.add(distribution_url)

            server_metadata_url = product.get("ServerMetadataURL")
            if server_metadata_url:
                metadata_urls.add(server_metadata_url)

        metadata = {}
        if not metadata_urls:
            return metadata

        with ThreadPoolExecutor(max_workers=min(8, len(metadata_urls))) as executor:
            futures = {
                executor.submit(network_handler.NetworkUtilities().get, url): url
                for url in metadata_urls
            }
            for future in as_completed(futures):
                response = future.result()
                if response:
                    metadata[futures[future]] = response.content
        return metadata

    @cached_property
    def products(self) -> None:
        """
        Returns a list of products from the sucatalog
        """

        catalog = self.catalog

        _products = []
        metadata = self._fetch_catalog_metadata(catalog["Products"])

        for product in catalog["Products"]:
            product_data = catalog["Products"][product]

            # InstallAssistants.pkgs (macOS Installers) will have the following keys:
            if self.ia_only:
                packages = catalog["Products"][product].get("Packages", [])
                has_legacy_install_assistant = any(
                    self._package_name(package.get("URL", "")) in {
                        self.LEGACY_INSTALL_ASSISTANT_PACKAGE,
                        self.LEGACY_INSTALL_ESD_PACKAGE,
                    }
                    for package in packages
                )
                if "ExtendedMetaInfo" not in catalog["Products"][product]:
                    if not has_legacy_install_assistant:
                        continue
                elif "InstallAssistantPackageIdentifiers" not in catalog["Products"][product]["ExtendedMetaInfo"]:
                    if not has_legacy_install_assistant:
                        continue
                elif "SharedSupport" not in catalog["Products"][product]["ExtendedMetaInfo"]["InstallAssistantPackageIdentifiers"]:
                    if not has_legacy_install_assistant:
                        continue

            _product_map = {
                "ProductID": product,
                "PostDate":  catalog["Products"][product]["PostDate"],
                "Title":     None,
                "Build":     None,
                "Version":   None,
                "Catalog":   None,

                # Optional keys if not InstallAssistant only:
                # "Packages": None,

                # Optional keys if InstallAssistant found:
                # "InstallAssistant": {
                #     "URL":       None,
                #     "Size":      None,
                #     "XNUMajor":  None,
                #     "IntegrityDataURL":  None,
                #     "IntegrityDataSize": None
                # },
            }

            # InstallAssistant logic
            if "Packages" in catalog["Products"][product]:
                packages = catalog["Products"][product]["Packages"]
                packages_by_name = {
                    self._package_name(package.get("URL", "")): package
                    for package in packages
                }
                # Add packages to product map if not InstallAssistant only
                if self.ia_only is False:
                    _product_map["Packages"] = packages
                for package in packages:
                    if "URL" in package:
                        package_name = self._package_name(package["URL"])
                        if package_name == "InstallAssistant.pkg":
                            _product_map["InstallAssistant"] = {
                                "URL":               package["URL"],
                                "Size":              package["Size"],
                                "IntegrityDataURL":  package["IntegrityDataURL"],
                                "IntegrityDataSize": package["IntegrityDataSize"],
                                "RequiresValidation": True,
                                "RequiresExtraction": True,
                            }
                        elif (
                            package_name == self.LEGACY_INSTALL_ESD_PACKAGE
                            and "InstallAssistant.pkg" not in packages_by_name
                        ):
                            missing_components = [
                                name for name in self.LEGACY_REQUIRED_COMPONENTS
                                if not packages_by_name.get(name, {}).get("URL")
                            ]
                            if missing_components:
                                _product_map = {}
                                break

                            legacy_components = []
                            for name in self.LEGACY_REQUIRED_COMPONENTS:
                                component = packages_by_name[name]
                                legacy_components.append({
                                    "URL": component["URL"],
                                    "Size": component.get("Size", 0),
                                    "IntegrityDataURL": component.get("IntegrityDataURL"),
                                    "IntegrityDataSize": component.get("IntegrityDataSize", 0),
                                })
                            _product_map["InstallAssistant"] = {
                                "URL":                  package["URL"],
                                "Size":                 package.get("Size", 0),
                                "IntegrityDataURL":     package.get("IntegrityDataURL"),
                                "IntegrityDataSize":    package.get("IntegrityDataSize", 0),
                                "LegacyInstaller":      True,
                                "LegacyComponents":     legacy_components,
                                "DirectDownload":       True,
                                "RequiresValidation":  True,
                                "RequiresExtraction":  True,
                            }
                        elif (
                            package_name == self.LEGACY_INSTALL_ASSISTANT_PACKAGE
                            and "InstallAssistant" not in _product_map
                        ):
                            _product_map["InstallAssistant"] = {
                                "URL":                  package["URL"],
                                "Size":                 package.get("Size", 0),
                                "IntegrityDataURL":     package.get("IntegrityDataURL"),
                                "IntegrityDataSize":    package.get("IntegrityDataSize", 0),
                                "LegacyInstaller":      True,
                            }

                        if package_name not in ["Info.plist", "com_apple_MobileAsset_MacSoftwareUpdate.plist"]:
                            continue

                        contents = metadata.get(package["URL"])
                        if not contents:
                            continue
                        try:
                            plist_contents = plistlib.loads(contents)
                        except plistlib.InvalidFileException:
                            continue

                        if plist_contents:
                            if self._package_name(package["URL"]) == "Info.plist":
                                result = self._legacy_parse_info_plist(plist_contents)
                            else:
                                result = self._parse_mobile_asset_plist(plist_contents)

                            if result == {"Missing VMM Support": True}:
                                _product_map = {}
                                break

                            _product_map.update(result)

            if _product_map == {}:
                continue

            if _product_map["Version"] is not None:
                _product_map["Title"] = self._build_installer_name(_product_map["Version"], _product_map["Catalog"])

            # Fall back to English distribution if no version is found
            if _product_map["Version"] is None:
                url = None
                if "Distributions" in catalog["Products"][product]:
                    if "English" in catalog["Products"][product]["Distributions"]:
                        url = catalog["Products"][product]["Distributions"]["English"]
                    elif "en" in catalog["Products"][product]["Distributions"]:
                        url = catalog["Products"][product]["Distributions"]["en"]

                if url is None:
                    continue

                contents = metadata.get(url)
                if not contents:
                    continue

                _product_map.update(self._parse_english_distributions(contents))

                if _product_map["Version"] is None:
                    server_metadata_url = product_data.get("ServerMetadataURL")
                    server_metadata_contents = metadata.get(server_metadata_url)
                    if server_metadata_contents:
                        try:
                            server_metadata_plist = plistlib.loads(server_metadata_contents)
                        except plistlib.InvalidFileException:
                            server_metadata_plist = {}

                        if "CFBundleShortVersionString" in server_metadata_plist:
                            _product_map["Version"] = server_metadata_plist["CFBundleShortVersionString"]


            if _product_map["Version"] is not None:
                # Check if version is newer than the max version
                if self.ia_only:
                    try:
                        if packaging.version.parse(_product_map["Version"]) > self.max_ia_version:
                            continue
                    except packaging.version.InvalidVersion:
                        pass

            if _product_map["Build"] is not None:
                if "InstallAssistant" in _product_map:
                    try:
                        # Grab first 2 characters of build
                        _product_map["InstallAssistant"]["XNUMajor"] = int(_product_map["Build"][:2])
                    except ValueError:
                        pass

            # If version is still None, set to 0.0.0
            if _product_map["Version"] is None:
                _product_map["Version"] = "0.0.0"

            install_assistant = _product_map.get("InstallAssistant")
            if (
                install_assistant
                and self._package_name(install_assistant.get("URL", "")) == self.LEGACY_INSTALL_ESD_PACKAGE
            ):
                try:
                    version = packaging.version.parse(_product_map["Version"])
                except packaging.version.InvalidVersion:
                    continue
                if not (
                    packaging.version.parse("10.13")
                    <= version
                    < packaging.version.parse("10.16")
                ):
                    continue

            _products.append(_product_map)

        _products.extend(self._official_legacy_products(_products))
        _products = sorted(_products, key=lambda x: self._version_sort_key(x["Version"]))

        return _products


    @cached_property
    def latest_products(self) -> list:
        """
        Returns a list of the latest products from the sucatalog
        """
        return self._list_latest_installers_only(self.products)