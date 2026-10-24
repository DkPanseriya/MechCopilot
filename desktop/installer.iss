; Inno Setup script: MechCopilot-Setup-<version>.exe from dist\MechCopilot (PyInstaller output).
; Per-user install: no administrator rights needed, which matters on locked-down company PCs.
; Build with desktop\build.ps1 (it passes /DAppVersion).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F1C6A52-3C4B-4E1E-9F0B-6A2D7C5E9B13}
AppName=MechCopilot
AppVersion={#AppVersion}
AppVerName=MechCopilot {#AppVersion}
AppPublisher=MechCopilot
AppPublisherURL=https://github.com/DkPanseriya/MechCopilot
AppSupportURL=https://github.com/DkPanseriya/MechCopilot/issues
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\MechCopilot
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=MechCopilot-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\MechCopilot.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Settings, API key and chats live in %LOCALAPPDATA%\MechCopilot and survive updates and uninstall.
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\MechCopilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MechCopilot"; Filename: "{app}\MechCopilot.exe"
Name: "{autodesktop}\MechCopilot"; Filename: "{app}\MechCopilot.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MechCopilot.exe"; Description: "{cm:LaunchProgram,MechCopilot}"; Flags: nowait postinstall skipifsilent
