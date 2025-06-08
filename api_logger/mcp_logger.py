import sys
import subprocess
import threading
import argparse
import os

LOG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)),"mcp_io.log")

parser = argparse.ArgumentParser(description="Wrap a command, passing STDIN and STDOUT verbatim, and log to a file.",
                                 usage="%(prog)s [options] <command> [args...]")


parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run with arguments")

open(LOG_FILE, 'w', encoding='utf-8')

args = parser.parse_args()

if len(sys.argv) == 2:
    parser.print_help(sys.stderr)
    sys.exit(1)

target_command = args.command

def forward_and_log_stdin(proxy_stdin, target_stdin, log_file):
    try:
        while True:
            line_bytes = proxy_stdin.readline()
            if not line_bytes:
                break

            try:
                line_str = line_bytes.decode('utf-8')
            except UnicodeDecodeError:
                line_str = f"Non-UTF-8 data: {line_bytes!r}"

            #
            log_file.write(f"Input: {line_str}")
            log_file.flush()

            target_stdin.write(line_bytes)
            target_stdin.flush()

    except Exception as e:
        try:
            log_file.write(f"Error in forwarding STDIN: {str(e)}\n")
            log_file.flush()
        except:
            pass
    
    finally:
        try:
            target_stdin.close()
            log_file.write("------- Target STDIN closed successfully.\n")
            log_file.flush()
        except Exception as e:
            log_file.write(f"Error closing target STDIN: {str(e)}\n")
            log_file.flush()


def forward_and_log_stdout(target_stdout, proxy_stdout, log_file):
    """Forward and log STDOUT from the target command to the proxy STDOUT."""
    try:
        while True:
            line_bytes = target_stdout.readline()
            if not line_bytes:
                break

            try:
                line_str = line_bytes.decode('utf-8')
            except UnicodeDecodeError:
                line_str = f"Non-UTF-8 data: {line_bytes!r}"

            log_file.write(f"Output: {line_str}")
            log_file.flush()

            proxy_stdout.write(line_bytes)
            proxy_stdout.flush()

    except Exception as e:
        try:
            log_file.write(f"Error in forwarding STDOUT: {str(e)}\n")
            log_file.flush()
        except:
            pass
    
    finally:
        try:
            log_file.flush()
        except:
            pass



process = None
log_f = None
exit_code = 1

try:
    log_f = open(LOG_FILE, 'a', encoding='utf-8')
    process = subprocess.Popen(
        target_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )

    stdin_thread = threading.Thread(
        target=forward_and_log_stdin,
        args=(sys.stdin.buffer, process.stdin, log_f),
        daemon=True
    )

    stdout_thread = threading.Thread(
        target=forward_and_log_stdout,
        args=(process.stdout, sys.stdout.buffer, log_f),
        daemon=True
    )

    def forward_and_log_stderr(target_stderr, proxy_stderr, log_file):
        """Forward and log STDERR from the target command."""
        try:
            while True:
                line_bytes = target_stderr.readline()
                if not line_bytes:
                    break

                try:
                    line_str = line_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    line_str = f"Non-UTF-8 data: {line_bytes!r}"

                log_file.write(f"Error: {line_str}")
                log_file.flush()
                proxy_stderr.write(line_bytes)
                proxy_stderr.flush()

        except Exception as e:
            try:
                log_file.write(f"Error in forwarding STDERR: {str(e)}\n")
                log_file.flush()
            except:
                pass
        finally:
            try:
                log_file.flush()
            except:
                pass

    stderr_thread = threading.Thread(
        target=forward_and_log_stderr,
        args=(process.stderr, sys.stderr, log_f),
        daemon=True
    )
    stdin_thread.start()
    stdout_thread.start()
    stderr_thread.start()

    process.wait()
    exit_code = process.returncode

    stdin_thread.join(timeout=1.0)
    stdout_thread.join(timeout=1.0)
    stderr_thread.join(timeout=1.0)

except Exception as e:
    print(f"MCP Logger Error: {str(e)}", file=sys.stderr)

    if log_f and not log_f.closed:
        try:
            log_f.write(f"MCP Logger Main Error: {str(e)}\n")
            log_f.flush()
        except:
            pass
    exit_code = 1

finally:
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=1.0)
        except:
            pass
        if process.poll() is None:
            try:
                process.kill()
            except:
                pass
    if log_f and not log_f.closed:
        try:
            log_f.close()
        except:
            pass
    sys.exit(exit_code)