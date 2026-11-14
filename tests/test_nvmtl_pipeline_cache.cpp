/* SPDX-License-Identifier: MIT */
#include "nmplugin/nvmtl_pipeline_cache_io.h"
#include <cassert>
int main()
{
    char path[] = "/tmp/nullarc-cache-test-XXXXXX";
    assert(mkdtemp(path));
    int dir = open(path, O_RDONLY | O_DIRECTORY);
    assert(nvmtl_pc_private_fd(dir, 1));
    assert(!fchmod(dir,0777)); assert(!nvmtl_pc_private_fd(dir,1)); assert(!fchmod(dir,0700));
    nvmtl_pc_identity id = {0x1002,0x1900,{1,2,3}};
    uint8_t blob[128] = {};
    uint32_t header[] = {32,1,id.vendor,id.device};
    memcpy(blob, header, sizeof header); memcpy(blob+16,id.uuid,16);
    assert(nvmtl_pc_crc("123456789",9) == 0xcbf43926u);
    assert(nvmtl_pc_write(dir,"cache",blob,sizeof blob,&id) == 0);
    size_t size = 0; void *loaded = nvmtl_pc_read(dir,"cache",&id,&size);
    assert(loaded && size == sizeof blob && !memcmp(loaded,blob,size)); free(loaded);
    nvmtl_pc_identity wrong = id; wrong.uuid[0]++;
    assert(!nvmtl_pc_read(dir,"cache",&wrong,&size) && !size);
    assert(!symlinkat("cache",dir,"link"));
    assert(!nvmtl_pc_read(dir,"link",&id,&size));
    assert(!linkat(dir,"cache",dir,"hard",0));
    assert(!nvmtl_pc_read(dir,"cache",&id,&size));
    assert(!unlinkat(dir,"hard",0));
    assert(!fchmodat(dir,"cache",0644,0));
    assert(!nvmtl_pc_read(dir,"cache",&id,&size));
    assert(!fchmodat(dir,"cache",0600,0));
    int file = openat(dir,"cache",O_WRONLY);
    uint8_t damage = 1;
    assert(pwrite(file,&damage,1,sizeof(nvmtl_pc_file_header)+80) == 1); close(file);
    assert(!nvmtl_pc_read(dir,"cache",&id,&size));
    assert(!nvmtl_pc_write(dir,"cache",blob,sizeof blob,&id));
    file = openat(dir,"cache",O_WRONLY); assert(!ftruncate(file,20)); close(file);
    assert(!nvmtl_pc_read(dir,"cache",&id,&size));
    assert(!nvmtl_pc_write(dir,"cache",blob,sizeof blob,&id));
    file = openat(dir,"cache",O_WRONLY); assert(!ftruncate(file,NVMTL_PC_MAX+128)); close(file);
    assert(!nvmtl_pc_read(dir,"cache",&id,&size));
    blob[4] = 2; assert(nvmtl_pc_write(dir,"cache",blob,sizeof blob,&id) == -1);
    assert(!unlinkat(dir,"link",0)); assert(!unlinkat(dir,"cache",0)); close(dir); assert(!rmdir(path));
    puts("[PASS] private cache roundtrip; UUID, symlink, hardlink, permissions, corruption and size rejection");
}
