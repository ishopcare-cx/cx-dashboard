' cx-dashboard scheduled task hidden launcher - runs the given .cmd with no visible console window.
' Arg0 = full path to the .cmd file to run. Returns its exit code to Task Scheduler.
Set sh = CreateObject("WScript.Shell")
cmdPath = WScript.Arguments(0)
rc = sh.Run("""" & cmdPath & """", 0, True)
WScript.Quit rc
