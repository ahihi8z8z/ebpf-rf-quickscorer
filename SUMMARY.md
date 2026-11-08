# Tóm tắt kết quả: QuickScorer cho RF trong eBPF/XDP

Cập nhật 2026-11-08. Chi tiết đầy đủ nằm trong `docs/pilot_report.md`.

## Kết luận chính

**NO-GO.** QuickScorer (QS) không có lợi thế nào so với RF if-else sinh code (G-RF) trong eBPF, xét về cả ba mặt:
- số cây nhúng được;
- tốc độ suy luận;
- hiệu năng end-to-end trên XDP.

Hai giả thuyết đều không được xác nhận:

| Giả thuyết | Kết quả |
|---|---|
| **H-model**: RF là điểm vận hành đáng giá so với DT/NN | Ủng hộ yếu. RF chỉ hơn DT trên D1 multiclass (bị ảnh hưởng bởi artefact) và D3 multiclass khi rừng rất lớn. |
| **H-runtime**: QS giúp RF triển khai được, hoặc chạy nhanh hơn, trong eBPF | Bác bỏ trên cả 3 dataset. |

## 1. E1: chất lượng model

**Thiết lập:** 17 feature số nguyên lấy tại packet thứ 8, chia train/test theo khối thời gian, 3 seed.

**Kết quả:**
- NN 16×16 int8 kém nhất ở mọi nơi:
  - binary: thấp hơn 0,02–0,03 macro-F1;
  - multiclass: thấp hơn 0,2–0,4.
- RF so với DT:
  - binary: chênh nhau không quá 0,02;
  - multiclass: RF chỉ hơn DT trên D1 (+0,03–0,04) và D3 với cây sâu (+0,034, model 78k node). Trên D2, DT tốt hơn mọi RF.
- Chất lượng RF bão hòa ở khoảng T = 64 cây.
- **Artefact trên D1:** capture có frame lớn hơn 1500 B do GRO/TSO, chiếm 99,7 % flow DDoS. Khi replay trên link thật, F1 của D1 chỉ còn 0,40–0,47.

## 2. E2: có nạp được model vào eBPF không (65 cấu hình RF)

Quét T = 16–512 cây, D = 4–12 hoặc tối đa 64 lá, trên D1–D3, cả binary lẫn multiclass.

| Họ runtime | Số cấu hình nạp được (trên 65) | Ghi chú |
|---|---|---|
| QS (mask / bounds / bpfloop) | 65 | |
| RF-walk (đọc node từ map) | 65 | |
| G-RF cũ | 52 | thất bại ở T ≥ 256 (E2BIG hoặc chạm 33 tail call) |
| **G-RF-x (generator đã sửa)** | **65, đều nằm gọn trong 1 chương trình, không cần tail call** | 0 lỗi trên 195 biến thể |

**Vì sao G-RF cũ thất bại.** Đây là lỗi của generator, không phải giới hạn của if-else:
- Feature được nạp vào biến cục bộ một lần. Sau mỗi phép so sánh, verifier thu hẹp miền giá trị của biến đó trên từng nhánh.
- Sang cây kế tiếp, các trạng thái mang miền giá trị khác nhau nên không gộp (prune) được, và số trạng thái bùng nổ.
- **Cách sửa:** đọc feature từ scratch (`volatile`) ngay tại mỗi phép so sánh.

**Kết quả của G-RF-x:**
- Chương trình lớn nhất cần khoảng 424k lệnh verifier phải duyệt; các model T512 cần 176k–345k. Giới hạn 1M không bị chạm ở đâu.
- Ngoại suy: một chương trình chứa được khoảng 2.500–3.000 cây 64 lá (chưa thử).

**Tốc độ (biến thể tốt nhất của mỗi họ):**

| So sánh | Trung vị | Khoảng |
|---|---|---|
| G-RF-x so với G-RF cũ | 0,71 (G-RF-x nhanh hơn) | 0,40–1,33 |
| QS so với G-RF-x | 12,4× chậm hơn | 2,5–1.919× |
| Walk so với G-RF-x | 4,9× chậm hơn | 1,9–9,6× |

- G-RF-x nhanh nhất trên 53/65 model.
- Ở 13 cấu hình T ≥ 256: G-RF-x mất 2,2–8,9 µs, QS mất 14,6–59 µs, walk mất 10,9–42 µs.

**Tập "chỉ QS nạp được" là rỗng.**

## 3. Code cũ của bạn: xdp-program, nhánh `random_forest` và `quickscore`

Đây là nguồn gốc của kết luận cũ "QS nhúng được nhiều cây hơn". Tôi đã build lại cả hai nhánh và nạp thử trên kernel 6.8.

| T | RF cũ (L16 / L64) | RF đã sửa (L16 / L64) | QS cũ (L16 / L64) |
|---|---|---|---|
| 10 | 26,6k / 33,2k | 4,9k / 5,8k | 8,6k / 17,6k |
| 20 | 602k / 244k | 8,9k / 12,1k | 27,9k / 45,9k |
| 50 | E2BIG / E2BIG | 20,8k / 29,1k | 156k / 223k |
| 100 | E2BIG / E2BIG | 41,3k / 54,7k | 631k / ✗ (*) |
| 200 | E2BIG / E2BIG | 79,2k / 110,8k | E2BIG / ✗ (*) |
| 500 | E2BIG / E2BIG | ✗ (*) / ✗ (*) | ✗ (*) / ✗ (*) |

Các ô là số lệnh verifier phải duyệt. (*) là lỗi "sequence of 8193 jumps is too complex": vòng lặp quá dài trên một đường thực thi. Đây là giới hạn chung của kernel, cả hai bên đều gặp.

**Phân tích:**
- Nhánh `random_forest` thực chất là **map-walk, không phải if-else**.
- Nó nổ trạng thái verifier vì `votes0`/`votes1` nằm trong thanh ghi và được so sánh ở cuối. Kết quả của mỗi cây tách trạng thái làm hai, nên số trạng thái nhân lên theo số cây.
- **Cách sửa:** cộng phiếu vào bộ nhớ map (`dp->label`). Sau khi sửa, số lệnh tăng tuyến tính, khoảng 400–550 lệnh mỗi cây, và RF vượt QS.

**Hai lỗi khác trong code cũ:**
1. Nhánh `quickscore` không reset `v[]` sau mỗi lần suy luận, và map dùng chung giữa các CPU. Từ flow thứ hai trở đi dự đoán sai, nên mọi số accuracy hay tỉ lệ drop đo trên nhánh này không đáng tin.
2. Nhánh `random_forest` tính `MAX_DEPTH = log2(2L−1) + 1`, tức là giả định cây cân bằng. Cây sâu hơn mức này bị cắt ngang và trả về benign.

Bản sửa và log nằm trong `results/xdpold/`.

## 4. E4/E4b: chi phí suy luận và cơ chế

Cùng model, cùng bảng dữ liệu, kết quả bit-exact. Tỉ lệ thời gian QS / walk (nhỏ hơn 1 nghĩa là QS nhanh hơn):

| | C, cold | eBPF, cold |
|---|---|---|
| 5 model mà QS thắng trong C | **0,73–0,92** (QS nhanh hơn) | 1,04–1,21 (QS chậm hơn) |
| QS so với G-RF | — | 4,5–20× chậm hơn |

"Cold" nghĩa là mỗi lần gọi dùng một dòng dữ liệu mới, sát với thực tế XDP. Harness E4 cũ dùng `repeat = 200` trên cùng một dòng, nên branch predictor đã "học" đường đi của walk. Điều này phóng đại khoảng cách QS/walk lên 1,2–1,7×, nhưng không làm đổi kết luận nào.

**Vì sao QS thắng trong C nhưng thua trong eBPF:**
1. **QS làm nhiều việc hơn.** Nó xử lý số node gấp 3–11 lần walk hoặc if-else. Trong C, QS bù lại bằng IPC: khoảng 3, so với 0,65–1,0 của walk, vốn bị nghẽn bởi chuỗi load phụ thuộc.
2. **eBPF làm phình số lệnh khoảng 2,8×.** Mỗi lần cập nhật bitvector tốn 25 lệnh x86 sau JIT, so với 9 lệnh khi gcc biên dịch.
   - 12/16 lệnh thừa đến từ ISA của BPF và JIT: không có scaled addressing, không có ALU hay compare với toán hạng bộ nhớ, phải sign-extend, dạng 2 toán hạng, thiếu thanh ghi, không có ctz.
   - Chỉ 4/16 lệnh thừa là do verifier ép (mask chỉ số, kiểm tra cận).
3. **Vòng lặp QS bị giới hạn bởi throughput nên chịu trọn phần phình này.** Walk bị giới hạn bởi độ trễ load nên "giấu" được phần phình của nó.
4. **If-else không có cả hai vấn đề.** Threshold là hằng số trong code, không có load bảng. Mỗi node chỉ tốn khoảng 5,5 lệnh và 3–4 cycle, và chỉ đi đúng đường từ gốc xuống lá.

**Những nguyên nhân đã kiểm tra và loại trừ:**
- Thiếu SIMD: tắt vector hóa trong C thì QS không đổi (2.294 so với 2.275 ns).
- Thao tác đọc-sửa-ghi (RMW) bitvector trong map: không phải chi phí chính. Đặt bitvector trên stack thì thậm chí không nạp được (E2BIG).
- Mask và kiểm tra cận của verifier: chỉ giải thích dưới 1/4 khoảng chênh.

## 5. E5: XDP end-to-end

- **Độ trung thực:** feature online bit-exact với ≥ 99,98 % flow. Dự đoán online trùng với offline 98–99,96 %.
- **Chất lượng khi replay có nhãn:** macro-F1 của RF bằng nhau ở cả ba runtime: D1 0,47, D2 0,88–0,89, D3 0,68–0,69.
- **D3 với model T64D12:** QS tốn khoảng 0,5 ms mỗi lần suy luận và **làm mất 15–25 % packet**. G-RF và walk chạy ngang mức của chương trình null chain (khoảng 250 ns mỗi packet, không mất packet).
- **D1/D2:** packet bị mất như nhau với mọi chương trình, kể cả null. Đó là giới hạn nhận packet của testbed, không liên quan tới classifier.
- **Điểm Pareto** ở mọi dataset luôn là DT hoặc G-RF, không bao giờ là QS.

## 6. QS ở userspace so với if-else

- **Chúng ta chưa đo if-else biên dịch bằng gcc.**
- Lợi thế của QS so với if-else trong bài báo gốc thuộc về chế độ hàng nghìn đến hơn 20 nghìn cây. Ở đó code if-else lên tới vài chục MB nên bị i-cache/iTLB miss, và nhánh đoán sai khoảng 50 %.
- Rừng ≤ 512 cây của chúng ta không ở chế độ đó.

**Có mang được lợi thế đó xuống eBPF không:**
- **Tối ưu QS** (lưu sẵn byte offset trong bảng, gộp dữ liệu thành bản ghi array-of-structs, `-mcpu=v4`, unroll theo từng feature) có thể giảm từ 25 xuống khoảng 13–15 lệnh. Khi đó QS có khả năng thắng walk, nhưng ước tính vẫn chậm hơn if-else 3–15×.
- **kfunc viết bằng C trong kernel module:** lấy lại được IPC như ở userspace, nhưng không còn là eBPF thuần.
- **Ngách hợp lý duy nhất:** model nằm trong map và cập nhật được lúc đang chạy mà không phải nạp lại chương trình. Khi đó đối thủ của QS là walk chứ không phải if-else.

## 7. Việc còn mở (chưa làm)

- Thêm if-else biên dịch bằng gcc vào `rfm.c` và đo trong C với T từ 64 đến khoảng 5.000 cây, để kiểm chứng lợi thế userspace của QS trên dữ liệu của chúng ta.
- Làm bản QS tối ưu trong eBPF và so với walk.
- Chạy lại E4 ở chế độ cold có thêm G-RF-x.
- Đo tốc độ của bản RF đã sửa (votes trong map) và của nhánh QS sau khi sửa lỗi reset `v[]`.

## File

| File | Nội dung |
|---|---|
| `docs/pilot_report.md` | Báo cáo đầy đủ: §2.1 G-RF-x, §5 cơ chế E4b |
| `docs/dataset_protocol.md` | Giao thức dữ liệu; §7 là artefact frame quá cỡ |
| `results/e2/deployability_matrix.csv`, `matrix.md` | Kết quả E2, có G-RF-x |
| `results/e4b/` | `mechanism.csv`, `regime.csv`, `code/` (xlated, JIT, gcc objdump) |
| `results/e5/xdp_performance.csv` | E5 |
| `results/xdpold/`, `code/xdpold/` | Sweep verifier trên code cũ và bản sửa RF |
| `docs/reproduce.md` | Cách reproduce từng thí nghiệm và các lưu ý khi thử nghiệm |
| `code/smoke.sh`, `sample/` | Smoke test offline không cần testbed |
