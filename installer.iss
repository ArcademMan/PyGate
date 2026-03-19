[Setup]
; Info applicazione
AppName=PyGate
AppVersion=1.0.0
AppPublisher=AmMstools
AppPublisherURL=https://github.com/AmMstools
DefaultDirName={autopf}\PyGate
DefaultGroupName=PyGate
OutputDir=installer_output
OutputBaseFilename=PyGate_Setup_1.0.0
Compression=lzma2
SolidCompression=yes
SetupIconFile=pygate.ico
UninstallDisplayIcon={app}\pygate.exe
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

; Permessi (installa senza admin se possibile)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia tutto il contenuto della cartella Nuitka standalone
Source: "dist\pygate.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menu Start
Name: "{group}\PyGate"; Filename: "{app}\pygate.exe"; IconFilename: "{app}\pygate.exe"
Name: "{group}\Uninstall PyGate"; Filename: "{uninstallexe}"
; Desktop (opzionale)
Name: "{userdesktop}\PyGate"; Filename: "{app}\pygate.exe"; IconFilename: "{app}\pygate.exe"; Tasks: desktopicon

[Run]
; Lancia l'app dopo l'installazione (opzionale)
Filename: "{app}\pygate.exe"; Description: "Launch PyGate"; Flags: nowait postinstall skipifsilent
