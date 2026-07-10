; Requires a live internet connection to install - this is a thin client
; that's non-functional without the hosted app anyway, and blocking an
; offline install stops the installer file being run in isolation on an
; air-gapped machine.
;
; customInit is called by electron-builder's NSIS template inside .onInit,
; before any files are extracted - see app-builder-lib/templates/nsis/installer.nsi.
!macro customInit
  DetailPrint "Checking internet connection..."
  InetC::get /NOCOOKIES /SILENT /CONNECTTIMEOUT 5 /RECEIVETIMEOUT 5 "https://api.mmnexus.co.za/health" "$TEMP\bfp_conncheck.tmp"
  Pop $0
  Delete "$TEMP\bfp_conncheck.tmp"
  ${If} $0 != "OK"
    MessageBox MB_ICONSTOP|MB_OK "BiznizFlowPilot needs an internet connection to install. Please connect to the internet and try again."
    Quit
  ${EndIf}
!macroend
