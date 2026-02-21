import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtGui import QStandardItemModel
from MacBoxTool.UIkit import *
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TreeView 组件模板示例")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        self.tree = SubtitleRadioButton("You're right","sss")
        layout.addWidget(self.tree)


    


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
