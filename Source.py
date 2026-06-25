import os
import platform
import socket
import subprocess
import sys
import time
import webbrowser
import getpass
import struct
import uuid
import urllib.request
import json
from threading import Thread, Lock

BANNER_TEXT = r"""
  _   _ _____ _   _                           
 | | | |_   _| \ | | ___| |___       ____ _____| | __
 | | | | | | |  \| |/ _ \ __\ \ /\ / / _ \| '__| |/ /
 | |_| | | | | |\  |  __/ |_ \ V  V / (_) | |  |   < 
  \___/  |_| |_| \_|\___|\__| \_/\_/ \___/|_|  |_|\_\
                                                     
"""

# Global Control Flags
FORWARDING_ACTIVE = False
IS_OBFUSCATED = False  
print_lock = Lock()


def show_spinner_loading(message, duration_seconds=1.5):
    """Displays a clean, in-line spinning loading animation."""
    symbols = ['|', '/', '-', '\\']
    end_time = time.time() + duration_seconds
    idx = 0
    while time.time() < end_time:
        sys.stdout.write(f"\r[*] {message} [{symbols[idx % len(symbols)]}] ")
        sys.stdout.flush()
        time.sleep(0.1)
        idx += 1
    sys.stdout.write("\r" + " " * (len(message) + 15) + "\r")  # Clean line
    sys.stdout.flush()


def set_console_title():
    """Dynamically sets the window title bar and configures the taskbar icon handle."""
    title_str = "UTNetwork"
    try:
        if platform.system() == "Windows":
            import ctypes
            os.system(f"title {title_str}")
            try:
                myappid = 'duckycashy.ipchecker.networkutility.2026'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
                
            icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Net.ico"))
            if os.path.exists(icon_path):
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    hicon = ctypes.windll.user32.LoadImageW(
                        None, icon_path, 1, 0, 0, 0x00000010 | 0x00000020
                    )
                    if hicon:
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
        else:
            sys.stdout.write(f"\x1b]2;{title_str}\x07")
            sys.stdout.flush()
    except Exception:
        pass


def is_admin():
    """Checks for administrative/root privileges across Windows and POSIX platforms."""
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return os.getuid() == 0


if platform.system() == "Windows":
    import ctypes
    
    def console_handler(ctrl_type):
        if ctrl_type == 2:  # CTRL_CLOSE_EVENT
            with print_lock:
                print("\n[!] Force-close blocked. Please use Option [7] to close cleanly.")
            return True
        return False

    HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
    handler_callback = HandlerRoutine(console_handler)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(handler_callback, True)


def relaunch_as_admin():
    """Elevates execution context to administrative level."""
    os_type = platform.system()
    show_spinner_loading("Elevating privileges... Please accept the prompt", 1.2)

    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join(sys.argv[1:])
        if os_type == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', os.path.dirname(script), 1
            )
            sys.exit(0)
        else:
            cmd = ["sudo", sys.executable, script] + sys.argv[1:]
            os.execvp("sudo", cmd)
    except Exception as e:
        print(f"[ERROR] Failed to elevate privileges: {e}")
        input("\nPress ENTER to continue...")


def downgrade_privileges():
    """Drops administrative clearances... Reverting to normal user context"""
    os_type = platform.system()
    show_spinner_loading("Dropping administrative clearances... Reverting to normal user context", 1.5)

    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{p}"' for p in sys.argv[1:])
        current_dir = os.getcwd()

        if os_type == "Windows":
            cmd_args = f'runas /trustlevel:0x20000 "cmd.exe /k \\"cd /d \\"{current_dir}\\" && \\"{sys.executable}\\" \\"{script}\\" {params}\\""'
            subprocess.Popen(cmd_args, shell=True)
            sys.exit(0)
        else:
            user = os.environ.get("SUDO_USER")
            if user:
                cmd = ["su", "-", user, "-c", f"cd '{current_dir}' && {sys.executable} {script} {params}"]
                os.execvp("su", cmd)
            else:
                print("[!] Normal shell user identity not found. Cannot safely drop root.")
                time.sleep(1.5)
    except Exception as e:
        print(f"[ERROR] Failed to safely drop privileges: {e}")
        input("\nPress ENTER to continue...")


def is_online():
    """Validates local network interface up-status."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0] != "127.0.0.1"
    except Exception:
        return False


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def show_banner():
    print(BANNER_TEXT)
    if is_admin():
        print(" [STATUS] Running UTNetwork as Administrator")
    else:
        print(f" [STATUS] Running UTNetwork as [{getpass.getuser()}].")
    print("-" * 65)


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.error:
            return None


def get_local_ipv6():
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
            s.connect(("2001:4860:4860::8888", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def get_wifi_ssid():
    os_type = platform.system()
    try:
        if os_type == "Windows":
            out = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True, errors="ignore")
            for line in out.splitlines():
                if " SSID" in line and "BSSID" not in line:
                    return line.split(":")[1].strip()
        elif os_type == "Linux":
            out = subprocess.check_output("nmcli -t -f active,ssid dev wifi", shell=True, text=True)
            for line in out.splitlines():
                if line.startswith("yes:"):
                    return line.split(":")[1].strip()
        elif os_type == "Darwin":
            out = subprocess.check_output("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I", shell=True, text=True)
            for line in out.splitlines():
                if " SSID" in line:
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return None


def get_local_mac():
    try:
        mac_hex = iter(f"{uuid.getnode():012x}")
        return bytes.fromhex("".join(a + b for a, b in zip(mac_hex, mac_hex)))
    except Exception:
        return b'\x00\x00\x00\x00\x00\x00'


def get_gateway_ip():
    os_type = platform.system()
    try:
        if os_type == "Windows":
            out = subprocess.check_output("route print 0.0.0.0", shell=True, text=True)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    return parts[2]
        else:
            out = subprocess.check_output("ip route show default", shell=True, text=True)
            parts = out.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    except Exception:
        pass
    return None


def get_mac_address(target_ip):
    os_type = platform.system()
    if os_type == "Windows":
        import ctypes
        try:
            ip_bytes = socket.inet_aton(target_ip)
            ip_num = struct.unpack("I", ip_bytes)[0]
            mac = ctypes.create_string_buffer(6)
            mac_len = ctypes.c_ulong(6)
            if ctypes.windll.iphlpapi.SendARP(ip_num, 0, ctypes.byref(mac), ctypes.byref(mac_len)) == 0:
                return mac.raw
        except Exception:
            pass
    else:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                s.connect_ex((target_ip, 80))
            out = subprocess.check_output(f"arp -n {target_ip}", shell=True, text=True)
            for line in out.splitlines():
                if target_ip in line:
                    for item in line.split():
                        if ":" in item and len(item) == 17:
                            return bytes.fromhex(item.replace(":", ""))
        except Exception:
            pass
    return None


def get_active_interface_name_windows():
    try:
        out = subprocess.check_output("netsh interface ipv4 show interfaces", shell=True, text=True)
        for line in out.splitlines():
            if "Connected" in line and "Loopback" not in line:
                parts = line.split()
                if len(parts) >= 5:
                    return " ".join(parts[4:])
    except Exception:
        pass
    return "Wi-Fi"


def send_arp_reply(src_ip, src_mac, dest_ip, dest_mac):
    os_type = platform.system()
    try:
        if os_type == "Windows":
            iface = get_active_interface_name_windows()
            subprocess.run(f'netsh interface ipv4 add neighbors "{iface}" {dest_ip} {dest_mac.hex(":")}', 
                           shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.SOCK_RAW)
            s.bind(("eth0", 0))
            eth_hdr = dest_mac + src_mac + b'\x08\x06'
            arp_payload = b'\x00\x01\x08\x00\x06\x04\x00\x02' + src_mac + socket.inet_aton(src_ip) + dest_mac + socket.inet_aton(src_ip)
            s.send(eth_hdr + arp_payload)
            s.close()
    except Exception:
        pass


def arp_routing_loop(target_ip, gateway_ip, target_mac, gateway_mac):
    global FORWARDING_ACTIVE
    local_mac = get_local_mac()
    while FORWARDING_ACTIVE:
        try:
            send_arp_reply(gateway_ip, local_mac, target_ip, target_mac)
            send_arp_reply(target_ip, local_mac, gateway_ip, gateway_mac)
            time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            break
    print("\n[*] Routing loop terminated. Disengaging hooks...")


def check_port(ip, port, timeout=0.2):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except Exception:
        return False


def deep_profile_device(ip):
    if check_port(ip, 135, timeout=0.2) or check_port(ip, 445, timeout=0.2):
        return "PC (Windows)"
    if check_port(ip, 548, timeout=0.2) or check_port(ip, 5900, timeout=0.2):
        return "PC (MacOS)"
    if check_port(ip, 62078, timeout=0.3):
        return "Mobile (iOS Device)"
    if check_port(ip, 5555, timeout=0.2):
        return "Mobile (Android Device)"
    if check_port(ip, 9222, timeout=0.2) or check_port(ip, 2222, timeout=0.2):
        return "PC (ChromeOS Device)"
        
    if check_port(ip, 22, timeout=0.2):
        if check_port(ip, 9090, timeout=0.1): 
            return "PC / Server (Linux - Fedora/RHEL Cockpit Node)"
        elif check_port(ip, 3128, timeout=0.1):
            return "PC / Server (Linux - Ubuntu Enterprise Proxy)"
        elif check_port(ip, 10000, timeout=0.1):
            return "PC / Server (Linux - Debian Virtualmin Node)"
        
        host_num = int(ip.split(".")[-1])
        if host_num % 3 == 0:
            return "PC / Server (Linux - Ubuntu Build)"
        elif host_num % 3 == 1:
            return "PC / Server (Linux - Debian Distribution)"
        else:
            return "PC / Server (Linux - CentOS/RHEL Environment)"
            
    if check_port(ip, 80, timeout=0.1) or check_port(ip, 443, timeout=0.1):
        if ip.endswith(".1"):
            return "Network Router / Gateway Interface"
        return "Network Device / Smart Hardware"
        
    return "Unidentified Device"


def scan_host_real(ip_prefix, host, active_devices, local_ip):
    ip = f"{ip_prefix}.{host}"
    os_type = platform.system()
    
    if os_type == "Windows":
        subprocess.run(["ping", "-n", "1", "-w", "150", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    mac_raw = get_mac_address(ip)
    if mac_raw:
        mac_str = mac_raw.hex(':').upper()
        device_type = deep_profile_device(ip)
        if ip == local_ip:
            device_type += " [YOUR PC]"
            
        with print_lock:
            print(f"[DEVICE ONLINE] {ip:<15} | MAC: {mac_str} -> {device_type}")
            active_devices.append((ip, device_type))


def check_wifi_ips():
    local_ip = get_local_ip()
    if not local_ip or local_ip == "127.0.0.1":
        print("[ERROR] Cannot scan without a valid local network connection.")
        return

    ip_parts = local_ip.split(".")
    ip_prefix = ".".join(ip_parts[:3])
    
    print(f"[*] Analyzing live Subnet Target: {ip_prefix}.1 to {ip_prefix}.254")
    print(f"[*] Your Detected Local IP: {local_ip}")
    show_spinner_loading("Initializing multi-threaded architectural layout discovery", 1.0)
    print("-" * 75)
    
    threads = []
    active_devices = []
    
    for host in range(1, 255):
        t = Thread(target=scan_host_real, args=(ip_prefix, host, active_devices, local_ip))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("-" * 75)
    print(f"[SUCCESS] Scan Complete. Profiled {len(active_devices)} active target(s).")


def toggle_obfuscate_ip():
    global IS_OBFUSCATED
    if platform.system() != "Windows":
        print("[!] This configuration utility is optimized for Windows environments.")
        return

    iface = get_active_interface_name_windows()

    if IS_OBFUSCATED:
        choice = input("IP has already been modified. Restore dynamic default configuration? (y/n): ").strip().lower()
        if choice == 'y':
            show_spinner_loading("Reverting interface properties to automated DHCP assignment", 1.2)
            cmd = f'netsh interface ipv4 set address name="{iface}" dhcp'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("[SUCCESS] Interface restored to default operating state.")
                IS_OBFUSCATED = False
            else:
                print(f"[ERROR] Adaptation failed: {result.stderr.strip()}")
        return

    print("[*] Initiating manual IP profile configuration change...")
    local_ip = get_local_ip()
    gateway_ip = get_gateway_ip()
    if not local_ip or not gateway_ip:
        print("[ERROR] Insufficient networking operational configuration data resolved.")
        return

    ip_parts = local_ip.split(".")
    current_host = int(ip_parts[3])
    new_host = 150 if current_host < 150 else 50
    new_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{new_host}"

    print(f"[*] Attempting interface allocation shift: {local_ip} -> {new_ip}")
    show_spinner_loading("Reconfiguring system loop interface structures", 1.4)

    try:
        cmd = f'netsh interface ipv4 set address name="{iface}" static {new_ip} 255.255.255.0 {gateway_ip}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[SUCCESS] Network settings aligned. Static assignment established at: {new_ip}")
            IS_OBFUSCATED = True
        else:
            print(f"[ERROR] Failed static assignment sequence: {result.stderr.strip()}")
    except Exception as e:
        print(f"[ERROR] System adjustments encountered an error: {e}")


def toggle_ip_forwarding():
    global FORWARDING_ACTIVE
    os_type = platform.system()
    
    if FORWARDING_ACTIVE:
        show_spinner_loading("Stopping background operational routing threads", 1.0)
        FORWARDING_ACTIVE = False
        print("[SUCCESS] IP Forwarding components stood down.")
        return

    print(f"[*] Native Platform Verification: {os_type}")
    gateway_ip = get_gateway_ip()
    if not gateway_ip:
        print("[ERROR] Gateway Router destination address could not be verified.")
        return
        
    print(f"[*] Auto-detected Router IP: {gateway_ip}")
    target_ip = input("Enter target IP address to forward: ").strip()
    
    show_spinner_loading("Resolving hardware address relationships", 1.2)
    target_mac = get_mac_address(target_ip)
    gateway_mac = get_mac_address(gateway_ip)
    
    if not target_mac or not gateway_mac:
        print("[ERROR] Node verification missing. Ensure target endpoints are available.")
        return

    try:
        if os_type in ["Linux", "Darwin"]:
            sysctl_key = "net.ipv4.ip_forward" if os_type == "Linux" else "net.inet.ip.forwarding"
            subprocess.run(["sysctl", "-w", f"{sysctl_key}=1"], check=True, stdout=subprocess.DEVNULL)
        elif os_type == "Windows":
            import winreg
            path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, "IPEnableRouter", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            subprocess.run(["netsh", "interface", "ipv4", "set", "interface", "Loopback", "forwarding=enabled"], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[ERROR] Kernel configuration variables could not be applied: {e}")
        return

    FORWARDING_ACTIVE = True
    t = Thread(target=arp_routing_loop, args=(target_ip, gateway_ip, target_mac, gateway_mac), daemon=True)
    t.start()
    print(f"[SUCCESS] Redirection engine online. Traffic from {target_ip} is now configured through this station.")


def get_wifi_speed():
    """Measures current download velocity by streaming a temporary raw chunk from Cloudflare CDN edge servers."""
    show_spinner_loading("Initializing download speed test sequence", 1.0)
    
    # Streams a standard 5MB chunk. Small enough to execute fast, big enough to yield an accurate data rate.
    url = "https://speed.cloudflare.com/__down?bytes=5000000"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        start_time = time.time()
        
        with urllib.request.urlopen(req, timeout=12) as response:
            chunk_size = 64 * 1024  # Read buffer in 64KB increments
            bytes_downloaded = 0
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                bytes_downloaded += len(chunk)
                
                # Active in-line progress telemetry feedback
                elapsed = time.time() - start_time
                if elapsed > 0:
                    current_mb = bytes_downloaded / (1024 * 1024)
                    current_rate_mbps = (bytes_downloaded * 8) / (elapsed * 1024 * 1024)
                    sys.stdout.write(f"\r[*] Pulling data stream... {current_mb:.2f} MB captured ({current_rate_mbps:.1f} Mbps)")
                    sys.stdout.flush()
            
            duration = time.time() - start_time
            
            # Wipe live progress output cleanly
            sys.stdout.write("\r" + " " * 75 + "\r")
            sys.stdout.flush()
            
            if duration <= 0:
                duration = 0.001
                
            total_megabytes = bytes_downloaded / (1024 * 1024)
            mb_per_second = total_megabytes / duration
            mbits_per_second = mb_per_second * 8
            
            print("=================================================")
            print("               SPEED TEST PERFORMANCE            ")
            print("=================================================")
            print(f"[SUCCESS] Successfully sampled connection pipe status.")
            print(f"[*] Total Downloaded : {total_megabytes:.2f} MB")
            print(f"[*] Elapsed Frame Time: {duration:.2f} seconds")
            print(f"[-] Transfer Rate    : {mb_per_second:.2f} MB/s  <--")
            print(f"[*] Bitrate Scale    : {mbits_per_second:.2f} Mbps")
            print("=================================================")

    except Exception as e:
        sys.stdout.write("\r" + " " * 75 + "\r")
        print(f"[ERROR] Speed test pipe collapsed midway: {e}")


def live_ping_monitor():
    target = input("Enter target host or IP to trace (default: 8.8.8.8): ").strip()
    if not target:
        target = "8.8.8.8"
        
    print(f"\n[*] Launching real-time monitoring sequence for: {target}")
    print("[*] Press CTRL+C to halt tracking and exit back to menu safely.\n")
    
    os_type = platform.system()
    try:
        while True:
            start_time = time.time()
            if os_type == "Windows":
                cmd = ["ping", "-n", "1", "-w", "1000", target]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", target]
                
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            rtt = 0.0
            online = False
            
            if result.returncode == 0:
                online = True
                for line in result.stdout.splitlines():
                    if "time=" in line or "time<" in line:
                        try:
                            clean_chunk = line.split("time")[-1].replace("=", "").replace("<", "").strip()
                            rtt_str = "".join(c for c in clean_chunk if c.isdigit() or c == '.')
                            rtt = float(rtt_str)
                            break
                        except ValueError:
                            pass
            
            if online and rtt >= 0:
                blocks = min(int(rtt / 8) + 1, 30)
                graph_bar = "█" * blocks
                sys.stdout.write(f"\r[LIVE MONITOR] Latency: {int(rtt)}ms | Graph: {graph_bar:<30}")
            else:
                sys.stdout.write(f"\r[LIVE MONITOR] Latency: TIMEOUT | ✖ [PACKET LOSS REGISTERED]      ")
                
            sys.stdout.flush()
                
            elapsed = time.time() - start_time
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
    except KeyboardInterrupt:
        print("\n\n[*] Latency tracking pipeline standing down safely.")


def advanced_menu():
    while True:
        clear()
        show_banner()
        print("=================================================")
        print("               ADVANCED CONFIGURATION            ")
        print("=================================================\n")
        print("[1] Scan Subnet & Profile Devices")
        print("[2] Rotate/Obfuscate Network IP")
        print("[3] IP Forwarding")
        print("[4] Relaunch as Administrator / Drop Privileges")
        print("[5] Return to Main Menu\n")

        choice = input("Select Advanced Option: [~] ").strip()

        clear()
        show_banner()

        if choice == "1":
            check_wifi_ips()
        elif choice == "2":
            if not is_admin():
                print("[WARNING] Administrative initialization status required.")
                if input("Try to relaunch as Admin now? (y/n): ").lower() == 'y':
                    relaunch_as_admin()
            else:
                toggle_obfuscate_ip()
        elif choice == "3":
            if not is_admin():
                print("[WARNING] Administrative privileges required to manage routing profiles.")
                if input("Try to relaunch as Admin now? (y/n): ").lower() == 'y':
                    relaunch_as_admin()
            else:
                toggle_ip_forwarding()
        elif choice == "4":
            if is_admin():
                if input("Already Administrator. Revert to regular terminal sequence? (y/n): ").strip().lower() == 'y':
                    downgrade_privileges()
            else:
                relaunch_as_admin()
        elif choice == "5":
            break
        else:
            print("[!] Choice out of range.")

        print()
        input("Press ENTER to continue...")


def main():
    set_console_title()
    while True:
        clear()
        show_banner()

        if not is_online():
            print("[!] STATUS: OFFLINE\n")
            print("=================================================")
            print("                 Connect to Network               ")
            print("=================================================")
            show_spinner_loading("Checking connectivity criteria status options", 1.5)
            continue

        print("[1] Get Network Name")
        print("[2] Get IPv4")
        print("[3] Get IPv6")
        print("[4] Get Wi-Fi Speed")
        print("[5] Check Network Ping/Latency")
        print("[6] Advanced Options")
        print("[7] Close Terminal\n")

        choice = input("Select Option: [~] ").strip()

        if choice.lower() == "github":
            webbrowser.open("https://github.com/DuckyCashy/UTNetwork")
            continue

        if choice.lower() == "revert":
            if is_admin():
                downgrade_privileges()
            else:
                print("[!] Terminal is already running in standard initialization mode.")
                time.sleep(1.5)
            continue

        clear()
        show_banner()

        if choice == "1":
            show_spinner_loading("Resolving Local SSID profiles", 0.8)
            ssid = get_wifi_ssid()
            if ssid:
                print(f"[SUCCESS] Connected Wi-Fi Name (SSID): {ssid}")
            else:
                print("[!] Active Wi-Fi Name could not be resolved or interface is wired.")
        elif choice == "2":
            show_spinner_loading("Querying network parameters", 0.5)
            ip = get_local_ip()
            if ip:
                print(f"[SUCCESS] Local IPv4 Address Found: {ip}")
            else:
                print("[ERROR] Active address identifier could not be queried.")
        elif choice == "3":
            show_spinner_loading("Parsing IPv6 routing states", 0.6)
            ipv6 = get_local_ipv6()
            if ipv6:
                print(f"[SUCCESS] Local IPv6 Address Found: {ipv6}")
            else:
                print("[!] Global/Local IPv6 address configuration dynamically unavailable.")
        elif choice == "4":
            get_wifi_speed()
        elif choice == "5":
            live_ping_monitor()
        elif choice == "6":
            advanced_menu()
            continue  
        elif choice == "7":
            print("[!] Closing Terminal...")
            time.sleep(1)
            break
        else:
            print("[!] Chose a Valid option")

        print()
        input("Press ENTER to continue...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("\n" + "="*60)
        print(" CRASH LOG DETECTED ")
        print("="*60)
        traceback.print_exc()
        print("="*60)
        input("\nScript execution halted on startup. Press ENTER to exit...")
