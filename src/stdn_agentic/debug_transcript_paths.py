"""
Debug script to diagnose transcript saving issues.

Current expected transcript location:
  - output/transcripts/
"""

import os
from pathlib import Path

print("\n" + "=" * 80)
print("DEBUGGING TRANSCRIPT PATH ISSUES")
print("=" * 80 + "\n")

# Current working directory
print("1. Current Working Directory (CWD):")
print(f"   {os.getcwd()}\n")

# Check where files are being created
test_file = Path("test_output.txt")
test_file.write_text("test")
print("2. Test file created at:")
print(f"   {test_file.resolve()}\n")
test_file.unlink()

# Check relative path resolution
relative_dir = Path("output/transcripts")
print("3. Relative path 'output/transcripts':")
print(f"   Resolves to: {relative_dir.resolve()}\n")

# Check if directory exists
if relative_dir.exists():
    print("   ✓ Directory EXISTS")
    files = list(relative_dir.glob("*.txt"))
    print(f"   Files in directory: {len(files)}")
    if files:
        for f in files[-3:]:
            print(f"     - {f.name}")
else:
    print("   ✗ Directory DOES NOT EXIST\n")
    print("   Creating it...")
    relative_dir.mkdir(parents=True, exist_ok=True)
    print(f"   ✓ Created at: {relative_dir.resolve()}\n")

# Check absolute path
project_root = Path(__file__).parent
print("4. Project Root (from script location):")
print(f"   {project_root.resolve()}\n")

absolute_dir = project_root / "output" / "transcripts"
print("5. Absolute path construction:")
print(f"   {absolute_dir.resolve()}\n")

if absolute_dir.exists():
    print("   ✓ Directory EXISTS")
    files = list(absolute_dir.glob("*.txt"))
    print(f"   Files in directory: {len(files)}")
    if files:
        print("   Latest files:")
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
            size = f.stat().st_size
            print(f"     - {f.name} ({size} bytes)")
else:
    print("   ✗ Directory DOES NOT EXIST")

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print("""
If files are NOT being saved:

1. Ensure DebateReporter is configured to write to output/transcripts:

   PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
   output_dir = str(PROJECT_ROOT / "output" / "transcripts")
   reporter = DebateReporter(output_dir=output_dir)

2. Check directory permissions are correct:

   ls -la output/transcripts/
   chmod 755 output/transcripts/

3. Ensure DebateReporter is instantiated ONCE or MULTIPLE TIMES consistently:

   # WRONG - Different paths each time
   for i in range(3):
       reporter = DebateReporter()  # Path might change!

   # CORRECT - Single instance
   reporter = DebateReporter(output_dir=...)
   for i in range(3):
       reporter.save_debate_transcript(...)

4. Add debugging to DebateReporter:

   print(f"Saving to: {filepath.resolve()}")
   assert filepath.parent.exists(), f"Directory does not exist: {filepath.parent}"
""")

print("=" * 80 + "\n")
