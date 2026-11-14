/* SPDX-License-Identifier: MIT */
#ifndef NVMTL_TIMING_H
#define NVMTL_TIMING_H
#include <stdint.h>

static inline uint64_t nvmtl_elapsed_ns(uint64_t begin, uint64_t end)
{
    return end > begin ? end - begin : 0;
}

/* Caller holds the submission profiler lock; completions may arrive out of order. */
static inline double nvmtl_submit_gap_us(uint64_t begin, uint64_t end, uint64_t *last)
{
    const double gap = *last ? (double)nvmtl_elapsed_ns(*last, begin) / 1000.0 : 0;
    if (end > *last) *last = end;
    return gap;
}
#endif
