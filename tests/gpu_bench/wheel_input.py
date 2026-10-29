"""Build an unrepaired pyluxcore wheel: stock wheel with the fork pyd, no vendored libs.

usage: wheel_input.py <stock pyluxcore wheel from PyPI> <fork pyluxcore.pyd> <out.whl> [<dll> ...]

Keeps the stock metadata and Python sources, drops `pyluxcore.libs/` and the
delvewheel patches, so `delvewheel repair` can vendor the fork's DLLs. Each
extra <dll> goes to `pyluxcore.libs/` under its own name: OIDN loads
`LuxOpenImageDenoise_device_cpu.dll` by name at run time, so it must keep
it, and `delvewheel repair --analyze-existing` then patches its imports to
the mangled names (otherwise its plain `tbb12.dll` import binds to the one
Blender has loaded and the process exits with ERROR_PROC_NOT_FOUND).
"""
import base64, hashlib, os, re, sys, zipfile

stock_whl, pyd, out_whl, *extra_dlls = sys.argv[1:]
# The stock __init__ files use LF or CRLF; keep the line ending in front of the block
patch_re = re.compile(r"(\r?\n)# start delvewheel patch.*?# end delvewheel patch\r?\n", re.S)

with zipfile.ZipFile(stock_whl) as zin, zipfile.ZipFile(out_whl, "w", zipfile.ZIP_DEFLATED) as zout:
    record_name = next(n for n in zin.namelist() if n.endswith(".dist-info/RECORD"))
    rows = []
    for info in zin.infolist():
        name = info.filename
        if (name.startswith("pyluxcore.libs/") or name == record_name or name.startswith(".load-order")
                or name.endswith(".dist-info/DELVEWHEEL")):
            continue
        if name == "pyluxcore/pyluxcore.pyd":
            data = open(pyd, "rb").read()
        elif name.endswith("__init__.py"):
            text = patch_re.sub(r"\1", zin.read(name).decode("utf-8"))
            assert "delvewheel" not in text, name
            data = text.encode("utf-8")
        else:
            data = zin.read(name)
        zout.writestr(name, data)
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(data)}")
    for dll in extra_dlls:
        name = "pyluxcore.libs/" + os.path.basename(dll)
        data = open(dll, "rb").read()
        zout.writestr(name, data)
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(data)}")
    rows.append(f"{record_name},,")
    zout.writestr(record_name, "\n".join(rows) + "\n")
print("wrote", out_whl)
