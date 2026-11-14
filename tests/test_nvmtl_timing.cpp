/* SPDX-License-Identifier: MIT */
#include "nmplugin/nvmtl_timing.h"
#include <cassert>
#include <cmath>
#include <cstdio>
int main()
{
    uint64_t last = 0;
    assert(nvmtl_submit_gap_us(1000000, 5000000, &last) == 0);
    assert(nvmtl_submit_gap_us(2000000, 3000000, &last) == 0);
    assert(last == 5000000);
    assert(nvmtl_submit_gap_us(6000000, 7000000, &last) == 1000);
    assert(nvmtl_submit_gap_us(4000000, 6500000, &last) == 0);
    assert(last == 7000000);
    assert(nvmtl_submit_gap_us(7000000, 7000000, &last) == 0);
    assert(nvmtl_elapsed_ns(UINT64_MAX, 0) == 0);
    assert(nvmtl_elapsed_ns(4, 9) == 5);
    uint64_t peak = last, state = 42;
    for (unsigned i = 0; i < 100000; ++i) {
        state = state * 6364136223846793005ull + 1;
        uint64_t end = 10000000 + (state % 1000000);
        uint64_t begin = end - (state % 2000000);
        double gap = nvmtl_submit_gap_us(begin, end, &last);
        assert(std::isfinite(gap) && gap >= 0 && gap < 10000);
        if (end > peak) peak = end;
        assert(last == peak);
    }
    puts("[PASS] overlapping and reordered submissions cannot wrap gaps or regress completion time");
}
