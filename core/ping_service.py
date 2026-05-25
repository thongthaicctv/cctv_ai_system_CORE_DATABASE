import subprocess
import platform
import re


def ping_host(ip):
    try:
        system = platform.system().lower()

        if system == "windows":
            cmd = ["ping", "-n", "1", "-w", "1000", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout.lower()

        if result.returncode == 0:
            latency = 1

            for line in output.splitlines():
                if "time=" in line:
                    try:
                        latency = int(
                            line.split("time=")[1]
                            .split("ms")[0]
                            .replace("<", "")
                            .strip()
                        )
                    except:
                        pass
                elif "time<" in line:
                    latency = 1
                else:
                    match = re.search(r"(\d+)\s*ms", line)
                    if match:
                        latency = int(match.group(1))

            return True, latency

        return False, 0

    except:
        return False, 0
