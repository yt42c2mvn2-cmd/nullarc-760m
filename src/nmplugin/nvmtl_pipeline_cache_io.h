/* SPDX-License-Identifier: MIT */
#ifndef NVMTL_PIPELINE_CACHE_IO_H
#define NVMTL_PIPELINE_CACHE_IO_H
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define NVMTL_PC_MAX (64u * 1024u * 1024u)
typedef struct { uint32_t vendor, device; uint8_t uuid[16]; } nvmtl_pc_identity;
typedef struct { uint32_t magic, version; uint64_t size; uint32_t crc, reserved; } nvmtl_pc_file_header;
static inline uint32_t nvmtl_pc_crc(const void *data, size_t size)
{
    const uint8_t *p = (const uint8_t *)data;
    uint32_t crc = ~0u;
    for (size_t i = 0; i < size; ++i) {
        crc ^= p[i];
        for (unsigned j = 0; j < 8; ++j) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}
static inline int nvmtl_pc_valid(const void *data, size_t size, const nvmtl_pc_identity *id)
{
    uint32_t h[4];
    if (!data || size < 32 || size > NVMTL_PC_MAX) return 0;
    memcpy(h, data, sizeof h);
    return h[0] >= 32 && h[0] <= size && h[1] == 1 && h[2] == id->vendor && h[3] == id->device &&
           !memcmp((const uint8_t *)data + 16, id->uuid, 16);
}
static inline int nvmtl_pc_private_fd(int fd, int directory)
{
    struct stat s;
    return fd >= 0 && !fstat(fd, &s) && s.st_uid == geteuid() && !(s.st_mode & 0077) &&
           (directory ? S_ISDIR(s.st_mode) : S_ISREG(s.st_mode) && s.st_nlink == 1);
}
static inline void *nvmtl_pc_read(int dir, const char *name, const nvmtl_pc_identity *id, size_t *size)
{
    *size = 0;
    int fd = openat(dir, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (!nvmtl_pc_private_fd(fd, 0)) { if (fd >= 0) close(fd); return NULL; }
    struct stat s;
    if (fstat(fd, &s) || s.st_size < (off_t)(sizeof(nvmtl_pc_file_header) + 32) ||
        s.st_size > (off_t)(NVMTL_PC_MAX + sizeof(nvmtl_pc_file_header))) { close(fd); return NULL; }
    void *data = malloc((size_t)s.st_size);
    if (!data) { close(fd); return NULL; }
    size_t at = 0;
    while (at < (size_t)s.st_size) {
        ssize_t n = read(fd, (uint8_t *)data + at, (size_t)s.st_size - at);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        at += (size_t)n;
    }
    close(fd);
    if (at != (size_t)s.st_size) { free(data); return NULL; }
    nvmtl_pc_file_header h;
    memcpy(&h, data, sizeof h);
    const size_t payload = at - sizeof h;
    if (h.magic != 0x4e565043u || h.version != 1 || h.reserved ||
        h.size != payload || !nvmtl_pc_valid((uint8_t *)data + sizeof h, payload, id) ||
        h.crc != nvmtl_pc_crc((uint8_t *)data + sizeof h, payload)) { free(data); return NULL; }
    memmove(data, (uint8_t *)data + sizeof h, payload); *size = payload;
    return data;
}
static inline int nvmtl_pc_write(int dir, const char *name, const void *data, size_t size, const nvmtl_pc_identity *id)
{
    if (!nvmtl_pc_valid(data, size, id)) return -1;
    static unsigned sequence;
    char tmp[80];
    snprintf(tmp, sizeof tmp, ".pipeline-%ld-%u", (long)getpid(), __atomic_add_fetch(&sequence, 1, __ATOMIC_RELAXED));
    int fd = openat(dir, tmp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return -1;
    nvmtl_pc_file_header h = {0x4e565043u, 1, size, nvmtl_pc_crc(data, size), 0};
    uint8_t *encoded = (uint8_t *)malloc(sizeof h + size);
    if (!encoded) { close(fd); unlinkat(dir, tmp, 0); return -1; }
    memcpy(encoded, &h, sizeof h); memcpy(encoded + sizeof h, data, size);
    size += sizeof h;
    size_t at = 0;
    while (at < size) {
        ssize_t n = write(fd, encoded + at, size - at);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        at += (size_t)n;
    }
    free(encoded);
    int ok = at == size && !fsync(fd);
    if (close(fd)) ok = 0;
    if (ok && renameat(dir, tmp, dir, name)) ok = 0;
    if (!ok) unlinkat(dir, tmp, 0);
    return ok ? 0 : -1;
}
#endif
