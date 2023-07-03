# coding:utf-8
import json
import os
import shutil
import time
import zipfile

from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar
from qfluentwidgets import (SettingCardGroup, PushSettingCard, ScrollArea, ExpandLayout, PrimaryPushSettingCard,
                            MessageBox, StateToolTip, ComboBoxSettingCard, setTheme, )

from common.config import cfg
from common.style_sheet import StyleSheet
from components.input_setting_card import PushEditSettingCard


class GenerateResourcepackInterface(ScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.stateTooltip = None
        self.processThread = None
        self.packFolder = cfg.get(cfg.workFolder)
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.packLabel = QLabel(self.tr("生成汉化资源包"), self)

        self.packFolderCard = PushSettingCard(
            self.tr('选择目录'),
            FIF.BOOK_SHELF,
            self.tr("汉化文件目录--默认为工作目录 自定义需子目录分类"),
            cfg.get(cfg.workFolder),
            self.scrollWidget
        )
        self.metaGroup = SettingCardGroup(
            self.tr("配置资源包信息"), self.scrollWidget)
        self.metaNameCard = PushEditSettingCard(
            self.tr('保存'),
            FIF.BRUSH,
            self.tr('资源包名称(可选)'),
            self.tr('不修改则使用默认配置,自定义请不要包含空格'),
            self.tr('Modpack-Localization-Pack'),
            cfg.metaName,
            self.metaGroup
        )
        self.metaDescCard = PushEditSettingCard(
            self.tr('保存'),
            FIF.BRUSH,
            self.tr('资源包介绍(可选)'),
            self.tr('不修改则使用默认配置'),
            self.tr('generated by &aModpackLocalizationTools'),
            cfg.metaDesc,
            self.metaGroup
        )
        self.metaVersionCard = ComboBoxSettingCard(
            cfg.gameVersion,
            FIF.GLOBE,
            self.tr('游戏版本'),
            self.tr('用于匹配此资源包对应的整合包游戏版本，大致范围正确即可'),
            texts=['1.6.1~1.8.9', '1.9~1.10.2', '1.11~1.12.2', '1.13~1.14.4', '1.15~1.16.1', '1.16.2~1.16.5',
                   '1.17~1.17.1', '1.18~1.18.2', '1.19~1.19.2', '1.19.3(22w42a~22w44a)',
                   '1.19.3(22w45a)~1.19.4(快照23w07a)', '1.19.4-pre1~1.20(快照23w13a)', '1.20(23w14a)~1.20(23w16a)',
                   '1.20(23w17a)~'],
            parent=self.metaGroup
        )
        # self.metaIconPathCard = PushSettingCard(
        #     self.tr('选择文件'),
        #     FIF.EMOJI_TAB_SYMBOLS,
        #     self.tr("资源包图标(可选)--不修改则使用默认图标，请务必确保文件名称为pack.png且尽量保证长宽一致"),
        #     cfg.get(cfg.iconPath),
        #     self.metaGroup
        # )
        self.funcGroup = SettingCardGroup(
            self.tr("执行操作"), self.scrollWidget)
        self.buttonBoxCard = PrimaryPushSettingCard(
            self.tr('生成资源包'),
            FIF.FEEDBACK,
            self.tr('开始生成'),
            self.tr('生成游戏可用资源包'),
            parent=self.funcGroup
        )
        self.__initWidget()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # initialize style sheet
        self.scrollWidget.setObjectName('scrollWidget')
        self.packLabel.setObjectName('packLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        # initialize layout
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.packLabel.move(36, 30)
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.metaGroup.addSettingCard(self.metaNameCard)
        self.metaGroup.addSettingCard(self.metaVersionCard)
        self.metaGroup.addSettingCard(self.metaDescCard)
        # self.metaGroup.addSettingCard(self.metaIconPathCard)
        self.funcGroup.addSettingCard(self.buttonBoxCard)
        self.expandLayout.addWidget(self.packFolderCard)
        self.expandLayout.addWidget(self.metaGroup)
        self.expandLayout.addWidget(self.funcGroup)

    def __connectSignalToSlot(self):
        cfg.appRestartSig.connect(self.__showRestartTooltip)
        cfg.themeChanged.connect(setTheme)
        self.packFolderCard.clicked.connect(self.__onPackFolderCardClicked)
        self.buttonBoxCard.clicked.connect(self.generate_resourcepack)

    def __showRestartTooltip(self):
        InfoBar.success(
            self.tr('更新成功'),
            self.tr('如未生效可以尝试重启软件'),
            duration=1500,
            parent=self
        )

    def __onPackFolderCardClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("自定义工作目录"), "./")
        if not folder:
            return
        self.packFolderCard.setContent(folder)
        self.packFolder = folder

    def generate_resourcepack(self):
        title = self.tr('注意')
        content = self.tr(
            "此操作会将工作目录下所有zh_cn文件打包。另外后续使用时，任务部分除资源包外还需将原任务替换为local目录下使用本地化键的任务！！！")
        window = MessageBox(title, content, self.window())
        if not window.exec():
            return
        self.stateTooltip = StateToolTip(
            self.tr('提取中'), self.tr('请耐心等待'), self.window())
        self.stateTooltip.move(self.stateTooltip.getSuitablePos())
        self.stateTooltip.show()
        self.processThread = ProcessThread(self.packFolder)
        self.processThread.finished.connect(self.on_process_finished)
        self.processThread.error.connect(self.on_process_failed)
        self.processThread.start()

    def on_process_finished(self):
        self.stateTooltip.setContent(
            self.tr('完成,文件已生成于工作同级目录下'))
        self.stateTooltip.setState(True)
        self.stateTooltip = None

    def on_process_failed(self, error_msg):
        # 隐藏进度条，恢复用户界面
        # self.progressBar.hide()
        # 弹出错误提示框
        InfoBar.error(
            self.tr('生成失败'),
            self.tr(error_msg),
            duration=10000,
            parent=self
        )
        print(error_msg)


class ProcessThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    packmeta = {
        "pack": {
            "pack_format": 4,
            "description": "generated by §3ModpackLocalizationTools"
        }
    }

    def __init__(self, work_folder):
        super().__init__()
        self.work_folder = work_folder
        self.packmeta["pack"]["pack_format"] = int(cfg.get(cfg.gameVersion))
        self.packmeta["pack"]["description"] = cfg.get(cfg.metaDesc)

    def run(self):
        try:
            for root, dirs, files in os.walk(self.work_folder):
                for file in files:
                    if "zh_cn" in file.lower() and '/old/' not in root:
                        if 'resourcepack' in root:
                            break
                        source_file = os.path.join(root, file)
                        relative_path = os.path.relpath(source_file, self.work_folder)
                        destination_file = os.path.join(self.work_folder, 'resourcepacks', 'assets',
                                                        relative_path)
                        os.makedirs(os.path.dirname(destination_file), exist_ok=True)
                        shutil.copy(source_file, destination_file)
            # 将pack.mcmeta写入资源包
            packmeta_path = os.path.join(self.work_folder, 'resourcepacks')
            os.makedirs(packmeta_path, exist_ok=True)
            time.sleep(0.1)
            with open(packmeta_path + '/pack.mcmeta', 'w', encoding='utf-8') as f:
                json.dump(self.packmeta, f, indent=4, ensure_ascii=False)
            time.sleep(0.1)
            # 加入资源包Logo图片
            logo = QtGui.QPixmap(f':/images/logo.png')
            logo.save(packmeta_path + '/pack.png')
            time.sleep(0.1)
            # 压缩为资源包
            with zipfile.ZipFile(cfg.get(cfg.metaName)+'.zip', 'w') as zipf:
                for root, dirs, files in os.walk(packmeta_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=packmeta_path)
                        zipf.write(file_path, arcname)

            shutil.rmtree(packmeta_path)

        except Exception as e:
            self.error.emit(str(e))
        else:
            self.finished.emit()