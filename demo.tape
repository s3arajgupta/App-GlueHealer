# VHS Tape for GlueHealer Terminal Showcase
# Requires VHS (https://github.com/charmbracelet/vhs)
# Run locally: vhs demo.tape

Output assets/demo.gif

Set FontSize 15
Set FontFamily "JetBrains Mono"
Set Width 1200
Set Height 720
Set Padding 24
Set Theme "Catppuccin Mocha"
Set WindowBar "Colorful"
Set WindowBarSize 36
Set TypingSpeed 35ms

# Initial pause
Sleep 1s

# Type demo command
Type "python -m gluehealer demo --auto-approve"
Sleep 600ms
Enter

# Allow pipeline to run and show RCA + Diff + Versioned Apply + Retry
Sleep 8s

# Pause on the final healed summary banner so viewers can read the stats
Sleep 4s
