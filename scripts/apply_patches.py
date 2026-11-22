#!/usr/bin/env python3

"""
AHbsolute patch installer for Telegram-Android.

Usage:
python3 scripts/apply_patches.py upstream

Required:
TG_API_ID
TG_API_HASH

The script fails loudly when required source modifications
cannot be applied. It does not silently skip missing features.
"""

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

if len(sys.argv) < 2:
    print("Usage: apply_patches.py <upstream_dir>")
sys.exit(1)

UP = Path(sys.argv[1]).resolve()

APP_ID = os.environ.get("TG_API_ID", "").strip()
APP_HASH = os.environ.get("TG_API_HASH", "").strip()
PKG = os.environ.get("AH_PACKAGE", "com.ahbsolute.app").strip()

failures = []
warnings = []


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def fail(message, required=True):
prefix = "FAIL: " if required else "WARN: "
print(prefix + message)

if required:
failures.append(message)
else:
warnings.append(message)


def read(path):
return path.read_text(encoding="utf-8")


def write(path, content):
path.write_text(content, encoding="utf-8")


def walk(filename=None, suffix=None):
for root, dirs, files in os.walk(UP):
dirs[:] = [
d for d in dirs
if d not in (".git", "build", ".gradle")
]

for filename_found in files:
if filename and filename_found == filename:
yield Path(root) / filename_found

elif suffix and filename_found.endswith(suffix):
yield Path(root) / filename_found


def one(filename):
results = list(walk(filename=filename))
return results[0] if results else None


def replace_once(pattern, replacement, content):
return re.subn(pattern, replacement, content, count=1)


# ---------------------------------------------------------
# Validate repository
# ---------------------------------------------------------

if not UP.exists():
print("ERROR: upstream directory does not exist")
sys.exit(1)

if not APP_ID or not APP_HASH or not APP_ID.isdigit():
fail(
"TG_API_ID / TG_API_HASH are missing or invalid"
)

if not re.fullmatch(r"[A-Za-z0-9_.]+", PKG):
fail("AH_PACKAGE is invalid")


# ---------------------------------------------------------
# 1. BuildVars: Telegram API credentials
# ---------------------------------------------------------

print("\n=== 1. BuildVars ===")

bv = one("BuildVars.java")

if not bv:
fail("BuildVars.java not found")

elif APP_ID and APP_HASH and APP_ID.isdigit():

content = read(bv)

content, n1 = replace_once(
r"(APP_ID\s*=\s*)\d+",
lambda m: m.group(1) + APP_ID,
content
)

content, n2 = replace_once(
r'(APP_HASH\s*=\s*)"[^"]*"',
lambda m: m.group(1) + '"' + APP_HASH + '"',
content
)

if n1 != 1 or n2 != 1:
fail("Could not update APP_ID / APP_HASH")

else:
write(bv, content)
print("OK: Telegram API credentials configured")


# ---------------------------------------------------------
# 2. applicationId
# ---------------------------------------------------------

print("\n=== 2. Application ID ===")

gradle_files = (
list(walk(suffix="build.gradle"))
+ list(walk(suffix="build.gradle.kts"))
)

gradle_count = 0

for gradle in gradle_files:

content = read(gradle)

patterns = [
r'(applicationId\s*=?\s*)["\']org\.telegram\.messenger[\w.]*["\']',
r'(applicationId\s*=?\s*)["\'][^"\']*telegram[^"\']*["\']',
]

updated = content
count = 0

for pattern in patterns:
updated, n = re.subn(
pattern,
lambda m: m.group(1) + '"' + PKG + '"',
updated
)
count += n

if count:
write(gradle, updated)
gradle_count += count

if gradle_count:
print(f"OK: applicationId updated ({gradle_count})")

sanyaukr:
else:
fail(
"applicationId not found. "
"Check the current Telegram Gradle configuration."
)


# ---------------------------------------------------------
# 3. Android manifests
# ---------------------------------------------------------

print("\n=== 3. Android manifests ===")

manifest_count = 0

for manifest in walk(filename="AndroidManifest.xml"):

content = read(manifest)

updated, count = re.subn(
r"org\.telegram\.messenger(?:\.web|\.beta)?\.permission\.",
"${applicationId}.permission.",
content
)

if count:
write(manifest, updated)
manifest_count += count

print(
"INFO: manifest permissions rewritten:",
manifest_count
)


# ---------------------------------------------------------
# 4. Application name
# ---------------------------------------------------------

print("\n=== 4. Application name ===")

name_count = 0

for strings in walk(filename="strings.xml"):

content = read(strings)

updated, count = re.subn(
r'(<string\s+name="AppName(?:Beta)?"[^>]*>)[^<]*(</string>)',
r'\g<1>AHbsolute\g<2>',
content
)

if count:
write(strings, updated)
name_count += count

if name_count:
print(f"OK: AHbsolute name configured ({name_count})")

else:
fail("AppName string not found")


# ---------------------------------------------------------
# 5. Google Services
# ---------------------------------------------------------

print("\n=== 5. Google Services ===")

google_services = os.environ.get(
"GOOGLE_SERVICES_JSON_PATH"
)

google_count = 0

for google_file in walk(filename="google-services.json"):

if google_services and Path(google_services).exists():

write(
google_file,
Path(google_services).read_text(encoding="utf-8")
)

print("OK: custom google-services.json installed")

else:

content = read(google_file)

updated = re.sub(
r'("package_name"\s*:\s*)"[^"]*"',
lambda m: m.group(1) + '"' + PKG + '"',
content
)

write(google_file, updated)

google_count += 1

if not google_count and not google_services:
print("INFO: no Google Services files found")


# ---------------------------------------------------------
# 6. Source structure diagnostics
# ---------------------------------------------------------

print("\n=== 6. Telegram source structure ===")

drawer_files = list(UP.rglob("*Drawer*"))

if drawer_files:
print("Drawer-related files:")

for path in drawer_files[:30]:
print(" ", path.relative_to(UP))

else:
print("INFO: no Drawer-named files found")


launch_files = list(UP.rglob("LaunchActivity.java"))

if launch_files:

for launch in launch_files:
print(
"FOUND LaunchActivity:",
launch.relative_to(UP)
)

else:
fail("LaunchActivity.java not found")


# ---------------------------------------------------------
# 7. Drawer integration
# ---------------------------------------------------------

print("\n=== 7. Drawer integration ===")

drawer_adapter = one("DrawerLayoutAdapter.java")

if not drawer_adapter:

fail(
"DrawerLayoutAdapter.java not found. "
"AHbsolute drawer integration requires adaptation "
"to the current Telegram source."
)

else:

print(
"INFO: DrawerLayoutAdapter found:",
drawer_adapter.relative_to(UP)
)

content = read(drawer_adapter)

if "ahbsoluteOrderItems" in content:
print("INFO: AHbsolute drawer ordering already present")
else:
fail(
"Drawer adapter exists, but its current resetItems "
"implementation has not been safely patched."
)


# ---------------------------------------------------------
# 8. LaunchActivity integration
# ---------------------------------------------------------

print("\n=== 8. LaunchActivity integration ===")

launch = one("LaunchActivity.java")

if launch:

content = read(launch)

sanyaukr:
if "AHbsolute.handleDrawerClick" in content:
print("INFO: AHbsolute drawer click handler already present")

elif "drawerLayoutAdapter.getId(position)" in content:
print(
"INFO: old drawer click hook location found; "
"manual integration is still required."
)

else:
fail(
"Current LaunchActivity does not match the old "
"AHbsolute drawer patch."
)


# ---------------------------------------------------------
# 9. ImageReceiver
# ---------------------------------------------------------

print("\n=== 9. ImageReceiver ===")

image_receiver = one("ImageReceiver.java")

if not image_receiver:

fail("ImageReceiver.java not found")

else:

content = read(image_receiver)

if "ahShape" in content:

print("INFO: AHbsolute ImageReceiver patch already present")

else:

fail(
"ImageReceiver has not been patched. "
"The current source needs a compatible draw() hook."
)


# ---------------------------------------------------------
# 10. ApplicationLoader
# ---------------------------------------------------------

print("\n=== 10. ApplicationLoader ===")

application_loader = one("ApplicationLoader.java")

if not application_loader:

fail(
"ApplicationLoader.java not found",
required=False
)

else:

content = read(application_loader)

if "AHbsolute.onAppStart" in content:

print("INFO: AHbsolute startup hook already present")

elif re.search(
r"public\s+void\s+onCreate\s*\(\s*\)",
content
):

print(
"INFO: ApplicationLoader.onCreate found; "
"startup hook still needs source-compatible integration."
)

else:

fail(
"ApplicationLoader.onCreate not found",
required=False
)


# ---------------------------------------------------------
# Result
# ---------------------------------------------------------

print("\n====================================")

if failures:

print(
f"FAILED: {len(failures)} required check(s) failed."
)

for message in failures:
print(" -", message)

print(
"\nAHbsolute patches are not fully compatible "
"with this Telegram source version."
)

sys.exit(1)

print("All required checks passed.")
print("====================================")
