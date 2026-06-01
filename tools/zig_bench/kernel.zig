// Build on macOS:  zig build-lib kernel.zig -dynamic -O ReleaseFast -femit-bin=libkernel_zig.dylib
// Same C ABI as kernel.c, so tools/zig_bench/run_bench.py loads it unchanged.
export fn sifta_pheromone_kernel(
    success: [*]const f64, recency: [*]const f64, traversal: [*]const f64,
    base: [*]const f64, tau: [*]f64, rho: f64, n: usize,
    out_sum: *f64, out_min: *f64,
) f64 {
    var sum: f64 = 0.0;
    var mn: f64 = 1e300;
    var checksum: f64 = 0.0;
    var i: usize = 0;
    while (i < n) : (i += 1) {
        var s = success[i]; if (s > 1.0) s = 1.0;
        var r = recency[i]; if (r > 1.0) r = 1.0;
        var t = traversal[i]; if (t > 1.0) t = 1.0;
        const factor = 0.5*s + 0.3*r + 0.2*t;
        var cost = base[i] * (1.0 - factor*0.5);
        if (cost < 0.0) cost = 0.0; if (cost > 10.0) cost = 10.0;
        tau[i] = tau[i] * (1.0 - rho);
        sum += cost; if (cost < mn) mn = cost;
        checksum += cost * @as(f64, @floatFromInt(i % 7 + 1));
    }
    out_sum.* = sum; out_min.* = mn; return checksum;
}
