import subprocess
import logging
import sys

class Install:
    def __init__(self):

        self.packages:list = ["PySide6","darkdetect","colorthief","scipy","pillow","termcolor","psutil"]

        self.version=str(sys.version_info.major)+"."+str(sys.version_info.minor)
            
        self.cnt=[]

        logging.info(f"Your Python Version: {self.version}")
        print(f"Your Python Version: {self.version}")

        self.install_packages()
    
    def show_packages(self):
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
            return True
        else:
            logging.warning("Some packages are not installed. ")
            print("Some packages are not installed. ")
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
        

            
        

    

