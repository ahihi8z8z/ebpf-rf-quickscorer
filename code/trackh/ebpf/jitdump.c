/* write the raw x86 JIT image of a pinned BPF program: sudo ./jitdump <pinned prog> <out.bin> */
#include <bpf/bpf.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    int fd = bpf_obj_get(argv[1]); if (fd < 0) { perror("obj_get"); return 1; }
    struct bpf_prog_info i; __u32 l = sizeof i; memset(&i, 0, sizeof i);
    if (bpf_prog_get_info_by_fd(fd, &i, &l)) { perror("info"); return 1; }
    __u32 n = i.jited_prog_len; unsigned char *b = malloc(n);
    memset(&i, 0, sizeof i); i.jited_prog_len = n; i.jited_prog_insns = (__u64)(unsigned long)b; l = sizeof i;
    if (bpf_prog_get_info_by_fd(fd, &i, &l)) { perror("info2"); return 1; }
    FILE *f = fopen(argv[2], "wb"); fwrite(b, 1, n, f); fclose(f); printf("%u bytes\n", n); return 0;
}
