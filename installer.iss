; 桌面待办 - Inno Setup 安装脚本

[Setup]
AppName=桌面待办
AppVersion=2.0
AppPublisher=桌面待办
DefaultDirName={autopf}\桌面待办
DefaultGroupName=桌面待办
UninstallDisplayIcon={app}\桌面待办.exe
OutputDir=installer_output
OutputBaseFilename=桌面待办_安装程序
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile=app图标.ico
; 允许用户自选安装路径
AllowNoIcons=yes
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\桌面待办\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app图标.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\桌面待办"; Filename: "{app}\桌面待办.exe"; IconFilename: "{app}\app图标.ico"
Name: "{autodesktop}\桌面待办"; Filename: "{app}\桌面待办.exe"; IconFilename: "{app}\app图标.ico"; Tasks: desktopicon
Name: "{group}\卸载桌面待办"; Filename: "{uninstallexe}"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Run]
Filename: "{app}\桌面待办.exe"; Description: "立即运行桌面待办"; Flags: nowait postinstall skipifsilent
