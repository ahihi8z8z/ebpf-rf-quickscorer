/* Minimal hardware-counter helper for the E4b mechanism study (bench.c --perf, rfm.c).
 * Six independent counting events on the calling thread, scaled by time_enabled/time_running
 * when the (virtual) PMU multiplexes. kernel=1 counts kernel mode only (BPF_PROG_TEST_RUN runs the
 * program in the syscall); kernel=0 counts user mode only. */
#pragma once
#include <linux/perf_event.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#define PC_N 6
static const char *pc_name[PC_N] = {"instructions", "cycles", "branches", "branch_misses", "l1d_loads", "l1d_load_misses"};
struct pc { int fd[PC_N]; double val[PC_N]; };

static int pc_open1(uint32_t type, uint64_t cfg, int kernel) {
    struct perf_event_attr a; memset(&a, 0, sizeof a);
    a.size = sizeof a; a.type = type; a.config = cfg; a.disabled = 1;
    a.exclude_hv = 1; a.exclude_kernel = !kernel; a.exclude_user = kernel;
    a.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
    return (int)syscall(__NR_perf_event_open, &a, 0, -1, -1, 0);
}
static void pc_open(struct pc *p, int kernel) {
    const uint64_t l1r = PERF_COUNT_HW_CACHE_L1D | (PERF_COUNT_HW_CACHE_OP_READ << 8);
    p->fd[0] = pc_open1(PERF_TYPE_HARDWARE, PERF_COUNT_HW_INSTRUCTIONS, kernel);
    p->fd[1] = pc_open1(PERF_TYPE_HARDWARE, PERF_COUNT_HW_CPU_CYCLES, kernel);
    p->fd[2] = pc_open1(PERF_TYPE_HARDWARE, PERF_COUNT_HW_BRANCH_INSTRUCTIONS, kernel);
    p->fd[3] = pc_open1(PERF_TYPE_HARDWARE, PERF_COUNT_HW_BRANCH_MISSES, kernel);
    p->fd[4] = pc_open1(PERF_TYPE_HW_CACHE, l1r | (PERF_COUNT_HW_CACHE_RESULT_ACCESS << 16), kernel);
    p->fd[5] = pc_open1(PERF_TYPE_HW_CACHE, l1r | (PERF_COUNT_HW_CACHE_RESULT_MISS << 16), kernel);
}
static void pc_start(struct pc *p) {
    for (int i = 0; i < PC_N; i++) if (p->fd[i] >= 0) { ioctl(p->fd[i], PERF_EVENT_IOC_RESET, 0); ioctl(p->fd[i], PERF_EVENT_IOC_ENABLE, 0); }
}
static void pc_stop(struct pc *p) {
    for (int i = 0; i < PC_N; i++) {
        p->val[i] = -1;
        if (p->fd[i] < 0) continue;
        ioctl(p->fd[i], PERF_EVENT_IOC_DISABLE, 0);
        uint64_t r[3];
        if (read(p->fd[i], r, sizeof r) == sizeof r && r[2]) p->val[i] = (double)r[0] * r[1] / r[2];
    }
}
/* append  ,"<prefix>instructions":x,...  (per-unit values) */
static int pc_json(char *buf, size_t n, const char *prefix, const struct pc *p, double units) {
    int k = 0;
    for (int i = 0; i < PC_N; i++)
        k += snprintf(buf + k, n - k, ",\"%s%s\":%.2f", prefix, pc_name[i], p->val[i] < 0 ? -1.0 : p->val[i] / units);
    return k;
}
