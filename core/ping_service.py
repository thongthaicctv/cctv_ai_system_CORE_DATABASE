import subprocess
import platform


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

        if f"reply from {ip}".lower() in output:
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

            return True, latency

        return False, 0

    except:
        return False, 0
