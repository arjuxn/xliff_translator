#define MyAppName "XLIFF Translator"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "XLIFF Translator"
#define MyAppExeName "XLIFF Translator.exe"

[Setup]

AppId={{7E1D6C8A-0E9B-4C6F-9E2A-4F2D8C7A1B35}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\XLIFF Translator
DefaultGroupName=XLIFF Translator

DisableProgramGroupPage=yes

OutputDir=installer-output
OutputBaseFilename=XLIFF-Translator-Setup

Compression=lzma2/max
SolidCompression=yes

WizardStyle=modern

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

Uninstallable=yes
UninstallDisplayName=XLIFF Translator

[Files]

; ------------------------------------------------------------
; Main application executable
; ------------------------------------------------------------

Source: "..\dist\XLIFF Translator\XLIFF Translator.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ------------------------------------------------------------
; PyInstaller runtime
;
; Exclude Python package metadata and license trees.
; These are not required at runtime.
; ------------------------------------------------------------

Source: "..\dist\XLIFF Translator\_internal\*"; \
    DestDir: "{app}\_internal"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Excludes: "*.pyc,*.pyo,*.dist-info\*"

[Icons]

Name: "{autoprograms}\XLIFF Translator"; \
    Filename: "{app}\{#MyAppExeName}"

Name: "{autodesktop}\XLIFF Translator"; \
    Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Tasks]

Name: "desktopicon"; \
    Description: "Create a desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; \
    Flags: unchecked

[Run]

Filename: "{app}\{#MyAppExeName}"; \
    Description: "Launch XLIFF Translator"; \
    Flags: nowait postinstall skipifsilent