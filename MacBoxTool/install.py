import subprocess
from .constants import Constants
import logging

class Install:
    def __init__(self,global_constants:Constants):
        self.constants = global_constants
        self.packages:list = ["PySide6","darkdetect","colorthief","scipy","pillow","termcolor"]

        self.cnt=[]

        self.install_packages()
    
    def show_packages(self):
        logging.info("Installing required packages...")
        
        for package in self.packages:
            run=subprocess.run(["pip3","show",package],capture_output=True,text=True)
            if "Package(s) not found" in run.stdout:
                self.cnt.append(package)
                logging.warning(f"{package} is not installed.")
            else:
                logging.info(f"{package} is already installed.")
        if len(self.cnt)==0:
            logging.info("All packages are already installed.")
            return True
        else:
            logging.warning("Some packages are not installed. ")
            return False
            
    def install_packages(self):
        a=self.show_packages()
        if a == True:
            pass
        else:
            logging.info("Installing packages...")
            for package in self.cnt:
                logging.info(f"Installing {package}...")
                subprocess.run(["pip3","install", package],capture_output=True,text=True)
            logging.info("All packages are installed.")
        

            
        

    

