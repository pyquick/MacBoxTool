from ..include import *
from .gui_support import DefGUI


class Config(QConfig):
    modelchose = OptionsConfigItem(
        "MainWindow", "ModelChose", "MacPro7,1", OptionsValidator(model_array.SupportedSMBIOS), restart=True)

class BuildOCPage(ScrollArea):

    def __init__(self,global_constants:Constants,ui_support:DefGUI=None,global_settings:GlobalSettings=None,parent=None):
        super().__init__()

        logging.info("######################")
        logging.info("#####gui_build:OK#####")
        logging.info("######################") 

        self.setObjectName("Build_For_Mac")
        
        self.constants=global_constants
        self.gui_support=ui_support
        self.settings=global_settings

        self.cfg=Config()

        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.scrollWidget.setStyleSheet("QWidget { background: transparent; }")

        self.settings.add_key("MODEL","N/A")

        self.model=self.constants.computer.real_model or self.settings.find_key("MODEL")

        self.init_ui()

    def init_ui(self):
        self.expandLayout.setContentsMargins(SPACING["xxlarge"], SPACING["xlarge"], SPACING["xxlarge"], SPACING["xlarge"])
        self.expandLayout.setSpacing(SPACING["large"])

        self.expandLayout.addWidget(self._create_title_label())
        
        self.expandLayout.addWidget(self.create_build_model_card())

        self.expandLayout.addStretch()

    def create_build_model_card(self):
        #build for mac
        
        self.card = ComboBoxSettingCard(
            configItem=self.cfg.modelchose,
            icon=FluentIcon.ZOOM,
            title="Build for models",
            content="Choose your model",
            texts=model_array.SupportedSMBIOS
        )
        if self.model not in model_array.SupportedSMBIOS:
            self.card.setEnabled(False)
        self.card.setValue(self.model)
        self.cfg.modelchose.valueChanged.connect(self.apply)
        return self.card
    def apply(self):
        self.settings.edit_key("MODEL",self.cfg.modelchose.value)
        
    def _create_title_label(self):
        title_label = SubtitleLabel("Build OC for Old Macs")
        
        return title_label

    
