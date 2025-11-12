"""
Debug script to diagnose transcript saving issues
"""

from pathlib import Path
import os

print("\n" + "="*80)
print("DEBUGGING TRANSCRIPT PATH ISSUES")
print("="*80 + "\n")

# Current working directory
print(f"1. Current Working Directory (CWD):")
print(f"   {os.getcwd()}\n")

# Check where files are being created
test_file = Path("test_output.txt")
test_file.write_text("test")
print(f"2. Test file created at:")
print(f"   {test_file.resolve()}\n")
test_file.unlink()

# Check relative path resolution
relative_dir = Path("debate_transcripts/results")
print(f"3. Relative path 'debate_transcripts/results':")
print(f"   Resolves to: {relative_dir.resolve()}\n")

# Check if directory exists
if relative_dir.exists():
    print(f"   ✓ Directory EXISTS")
    files = list(relative_dir.glob("*.txt"))
    print(f"   Files in directory: {len(files)}")
    if files:
        for f in files[-3:]:
            print(f"     - {f.name}")
else:
    print(f"   ✗ Directory DOES NOT EXIST\n")
    print(f"   Creating it...")
    relative_dir.mkdir(parents=True, exist_ok=True)
    print(f"   ✓ Created at: {relative_dir.resolve()}\n")

# Check absolute path
project_root = Path(__file__).parent
print(f"4. Project Root (from script location):")
print(f"   {project_root.resolve()}\n")

absolute_dir = project_root / "debate_transcripts" / "results"
print(f"5. Absolute path construction:")
print(f"   {absolute_dir.resolve()}\n")

if absolute_dir.exists():
    print(f"   ✓ Directory EXISTS")
    files = list(absolute_dir.glob("*.txt"))
    print(f"   Files in directory: {len(files)}")
    if files:
        print(f"   Latest files:")
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
            size = f.stat().st_size
            mtime = f.stat().st_mtime
            print(f"     - {f.name} ({size} bytes)")
else:
    print(f"   ✗ Directory DOES NOT EXIST")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
print("""
If files are NOT being saved:

1. Check if DebateReporter is using ABSOLUTE paths:
   
   PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
   output_dir = str(PROJECT_ROOT / "debate_transcripts" / "results")
   reporter = DebateReporter(output_dir=output_dir)

2. Check if directory permissions are correct:
   
   ls -la debate_transcripts/results/
   chmod 755 debate_transcripts/results/

3. Check if DebateReporter is being instantiated ONCE or MULTIPLE TIMES:
   
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

print("="*80 + "\n")
