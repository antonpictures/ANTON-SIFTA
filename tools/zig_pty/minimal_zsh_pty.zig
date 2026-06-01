// Minimal Zig PTY proof for zsh on macOS (r247)
// Compile: zig build-exe minimal_zsh_pty.zig -lc
// Run: ./minimal_zsh_pty
// This demonstrates a native PTY arm as alternative to Python's pty.openpty()
// Goal: lower overhead, better signal handling, no Python 3.14 GC reentrancy issues.

const std = @import("std");
const c = @cImport({
    @cInclude("util.h");      // openpty, forkpty on macOS/BSD
    @cInclude("unistd.h");
    @cInclude("sys/ioctl.h"); // TIOCSCTTY
    @cInclude("sys/wait.h");
    @cInclude("signal.h");    // kill, SIGTERM
});

pub fn main() !void {
    var master_fd: c_int = undefined;
    var slave_fd: c_int = undefined;

    // Open a new pseudo-terminal pair
    if (c.openpty(&master_fd, &slave_fd, null, null, null) != 0) {
        std.debug.print("openpty failed\n", .{});
        return error.PtyOpenFailed;
    }
    defer _ = c.close(master_fd);

    const pid = c.fork();
    if (pid < 0) {
        std.debug.print("fork failed\n", .{});
        return error.ForkFailed;
    }

    if (pid == 0) {
        // Child: become session leader, attach to slave as controlling terminal
        _ = c.setsid();
        // TIOCSCTTY is in sys/ioctl.h on macOS
        const TIOCSCTTY = 0x20007484; // macOS value
        _ = c.ioctl(slave_fd, TIOCSCTTY, @as(c_int, 0));

        // Redirect stdio to the slave pty
        _ = c.dup2(slave_fd, c.STDIN_FILENO);
        _ = c.dup2(slave_fd, c.STDOUT_FILENO);
        _ = c.dup2(slave_fd, c.STDERR_FILENO);
        if (slave_fd > 2) _ = c.close(slave_fd);

        // Exec zsh
        const argv = [_:null]?[*:0]const u8{ "/bin/zsh", "-i", null };
        const envp = [_:null]?[*:0]const u8{null};
        _ = c.execve("/bin/zsh", @ptrCast(&argv), @ptrCast(&envp));

        // If exec fails
        std.debug.print("execve zsh failed\n", .{});
        c._exit(1);
    }

    // Parent: close slave, talk to master
    _ = c.close(slave_fd);

    std.debug.print("Zig PTY master fd={d}, child pid={d}\n", .{ master_fd, pid });

    // Simple proof: send "echo ZIG_PTY_OK\n" and read some output
    const cmd = "echo ZIG_PTY_OK\n";
    _ = c.write(master_fd, cmd.ptr, cmd.len);

    var buf: [256]u8 = undefined;
    const n = c.read(master_fd, &buf, buf.len);
    if (n > 0) {
        const output = buf[0..@intCast(n)];
        std.debug.print("Received from zsh PTY: {s}\n", .{output});
    }

    // Clean shutdown (in real arm we would proxy full duplex with signals)
    _ = c.kill(pid, c.SIGTERM);
    var status: c_int = 0;
    _ = c.waitpid(pid, &status, 0);

    std.debug.print("Zig minimal PTY proof complete. Master closed.\n", .{});
}