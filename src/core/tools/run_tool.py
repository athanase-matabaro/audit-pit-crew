# src/core/tools/run_tool.py
import subprocess, tempfile, json, os

def run_tool(cmd, cwd=None, timeout=600):
    outf = tempfile.NamedTemporaryFile(delete=False)
    errf = tempfile.NamedTemporaryFile(delete=False)
    try:
        rc = subprocess.call(cmd, cwd=cwd, stdout=open(outf.name,'wb'), stderr=open(errf.name,'wb'), timeout=timeout)
    except Exception as e:
        rc = 255
        open(errf.name,'a').write(str(e))
    stdout = open(outf.name,'rb').read()
    stderr = open(errf.name,'rb').read()
    return rc, stdout, stderr, outf.name, errf.name

def parse_json_output(stdout_bytes):
    if not stdout_bytes.strip():
        raise ValueError("No stdout")
    return json.loads(stdout_bytes)
