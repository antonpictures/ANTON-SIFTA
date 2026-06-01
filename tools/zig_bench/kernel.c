/* C reference of the SIFTA pheromone/forager hot kernel — ABI-identical to the Zig version,
   so this proves the FFI + byte-identical test harness with the cc already on disk. The real
   Zig measurement uses kernel.zig (same signature) on the owner's Mac. */
#include <stddef.h>
double sifta_pheromone_kernel(const double* success, const double* recency,
                              const double* traversal, const double* base,
                              double* tau, double rho, size_t n,
                              double* out_sum, double* out_min) {
    double sum = 0.0, mn = 1e300, checksum = 0.0;
    for (size_t i = 0; i < n; i++) {
        double s = success[i];   if (s > 1.0) s = 1.0;
        double r = recency[i];   if (r > 1.0) r = 1.0;
        double t = traversal[i]; if (t > 1.0) t = 1.0;
        double factor = 0.5*s + 0.3*r + 0.2*t;          /* GraphPalace cost.rs factor */
        double cost = base[i] * (1.0 - factor*0.5);     /* <=50% discount */
        if (cost < 0.0) cost = 0.0; if (cost > 10.0) cost = 10.0;
        tau[i] = tau[i] * (1.0 - rho);                  /* decay.rs exponential decay */
        sum += cost; if (cost < mn) mn = cost;
        checksum += cost * (double)(i % 7 + 1);
    }
    *out_sum = sum; *out_min = mn; return checksum;
}
