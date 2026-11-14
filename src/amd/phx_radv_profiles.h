#ifndef PHX_RADV_PROFILES_H
#define PHX_RADV_PROFILES_H
#include "phx_topology.h"
static inline int phx_apply_profile_device_info(const struct phx_topology *p, struct drm_amdgpu_info_device *di) {
    if (!di || !phx_topology_valid(p)) return 0;
    if (phx_topology_matches(p, 0x1002u, 0x1900u, 0xcau, 0x103cu, 0x8c6au)) {
        if (p->num_shader_engines != 1u) return 0;
        if (p->num_shader_arrays_per_engine != 2u) return 0;
        if (p->num_cu_per_sh != 6u) return 0;
        if (p->num_rb_pipes != 4u) return 0;
        if (p->enabled_rb_pipes_mask != 10u) return 0;
        if (p->cu_active_number != 8u) return 0;
        if (p->cu_bitmap[0][0] != 15u) return 0;
        if (p->cu_bitmap[0][1] != 15u) return 0;
        if (p->cu_bitmap[0][2] != 0u) return 0;
        if (p->cu_bitmap[0][3] != 0u) return 0;
        if (p->cu_bitmap[1][0] != 0u) return 0;
        if (p->cu_bitmap[1][1] != 0u) return 0;
        if (p->cu_bitmap[1][2] != 0u) return 0;
        if (p->cu_bitmap[1][3] != 0u) return 0;
        if (p->cu_bitmap[2][0] != 0u) return 0;
        if (p->cu_bitmap[2][1] != 0u) return 0;
        if (p->cu_bitmap[2][2] != 0u) return 0;
        if (p->cu_bitmap[2][3] != 0u) return 0;
        if (p->cu_bitmap[3][0] != 0u) return 0;
        if (p->cu_bitmap[3][1] != 0u) return 0;
        if (p->cu_bitmap[3][2] != 0u) return 0;
        if (p->cu_bitmap[3][3] != 0u) return 0;
        di->chip_rev = 12ull;
        di->external_rev = 13ull;
        di->family = 148ull;
        di->gpu_counter_freq = 100000ull;
        di->max_engine_clock = 2600000ull;
        di->max_memory_clock = 800000ull;
        di->vram_type = 12ull;
        di->vram_bit_width = 128ull;
        di->num_hw_gfx_contexts = 8ull;
        di->wave_front_size = 32ull;
        di->num_shader_visible_vgprs = 1024ull;
        di->num_tcc_blocks = 4ull;
        di->gs_vgt_table_depth = 32ull;
        di->gs_prim_buffer_depth = 1792ull;
        di->max_gs_waves_per_vgt = 32ull;
        di->gc_double_offchip_lds_buf = 0ull;
        di->pa_sc_tile_steering_override = 0ull;
        di->tcc_disabled_mask = 0ull;
        di->tcp_cache_size = 32ull;
        di->num_sqc_per_wgp = 1ull;
        di->sqc_data_cache_size = 16ull;
        di->sqc_inst_cache_size = 32ull;
        di->gl1c_cache_size = 256ull;
        di->gl2c_cache_size = 2048ull;
        di->mall_size = 0ull;
        return 1;
    }
    return 0;
}
#endif
