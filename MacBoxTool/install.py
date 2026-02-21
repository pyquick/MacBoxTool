import subprocess
import logging
import sys

from .support.global_settings import GlobalSettings
from .constants import Constants


class Install:
    def __init__(self):
        self.constants:Constants=Constants()
        self.settings=GlobalSettings(self.constants)
        self.packages:list = ["PySide6","darkdetect","colorthief","scipy","pillow","termcolor","psutil"]
        self.version=str(sys.version_info.major)+"."+str(sys.version_info.minor)

        self.installed = self.settings.find_key("INSTALLED")  
        self.last_version = self.settings.find_key("PYTHON_VERSION") or self.version   
            
        self.cnt=[]

        logging.info(f"Your Python Version: {self.version}")
        print(f"Your Python Version: {self.version}")

        logging.info(f"Last Python Version: {self.last_version}")
        print(f"Last Python Version: {self.last_version}")

        self.install_packages()

    def check_already_installed(self):
        if self.settings.find_key("PYTHON_VERSION") is None:
            self.settings.add_key("PYTHON_VERSION",str(self.version))
            return False
        if self.installed is None:
            self.installed= "NO"
            self.settings.add_key("INSTALLED","NO")
            return False
        if self.installed=="YES" and str(self.version) == str(self.last_version):
            return True
    
    def show_packages(self):
        if self.check_already_installed():
            logging.info("All packages are already installed.")
            print("All packages are already installed.")
            return True

        logging.info("Installing required packages...")
        print("Installing required packages...")
        
        for package in self.packages:
            run=subprocess.run([f"pip{self.version}","show",package],capture_output=True,text=True)
            if "Package(s) not found" in run.stdout or "Package(s) not found" in run.stderr:
                self.cnt.append(package)
                logging.warning(f"{package} is not installed.")
                print(f"{package} is not installed.")
            else:
                logging.info(f"{package} is already installed.")
                print(f"{package} is already installed.")
        if len(self.cnt)==0:
            logging.info("All packages are already installed.")
            print("All packages are already installed.")
            self.settings.edit_key("INSTALLED","YES")
            self.settings.edit_key("PYTHON_VERSION",self.version)
            return True
        else:
            logging.warning("Some packages are not installed. ")
            print("Some packages are not installed. ")
            self.settings.edit_key("PYTHON_VERSION",self.version)
            return False
            
    def install_packages(self):
        a=self.show_packages()
        if a == True:
            pass
        else:
            logging.info("Installing packages...")
            print("Installing packages...")
            for package in self.cnt:
                logging.info(f"Installing {package}...")
                print(f"Installing {package}...")
                process=subprocess.Popen([f"pip{self.version}","install", package],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
                for line in process.stdout:
                    print(line.strip())
                    sys.stdout.flush()
                process.wait()
            logging.info("All packages are installed.")
            print("All packages are installed.")
            self.settings.edit_key("INSTALLED","YES")
            self.settings.edit_key("PYTHON_VERSION",self.version)
        

            
        

    

