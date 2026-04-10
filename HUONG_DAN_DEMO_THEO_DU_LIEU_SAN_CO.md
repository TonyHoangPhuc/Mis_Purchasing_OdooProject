# Hướng Dẫn Demo Cực Chi Tiết Dựa Trên Dữ Liệu Đã Có Sẵn

Tài liệu này được viết theo đúng dữ liệu hiện đang có trong hệ thống của bạn, để người dùng:

1. mở dữ liệu đã có sẵn để đọc hiểu nhanh
2. sau đó tự tạo mới theo đúng mẫu đang có

Tài liệu chia làm 2 luồng:

- Luồng 1: demo toàn bộ bằng `admin`
- Luồng 2: demo theo từng role, mỗi người đăng nhập một tài khoản khác nhau

## 1. Dữ liệu đang có sẵn trong hệ thống

Phần này rất quan trọng. Khi demo, bạn nên dùng chính dữ liệu này để giải thích trước, sau đó mới tạo mới.

### 1.1. Kho hiện có

Hệ thống hiện đang có 3 kho:

- `My Company`
- `WH-HCM`
- `WH-DC`

Trong đó:

- `WH-HCM` là kho nhận
- `WH-DC` là kho nguồn để cấp nội bộ

### 1.2. Sản phẩm hiện có

Hiện có 2 sản phẩm demo:

- `Burger`
- `Eggs`

### 1.3. Đối tác hiện có

Hiện có các đối tác quan trọng:

- `NCC ABC`: nhà cung cấp dùng cho flow mua ngoài
- `Store`: cửa hàng dùng cho flow cấp nội bộ

`Store` hiện đang là:

- `Is Store = True`
- `Store Priority = high`

### 1.4. Quy tắc phân bổ hiện có

Đã có 1 allocation rule:

- `Store`: `Store`
- `Warehouse`: `WH-DC`
- `Location`: `WH-HC/Store Q1 Stock`
- `Product`: `Eggs`
- `Min Qty = 10`
- `Max Qty = 10`

### 1.5. Chứng từ MER đang có sẵn

Hiện có 2 MER quan trọng:

#### MER mua ngoài

- `MER/2026/0001`
- trạng thái: `po_created`
- kho nhận: `WH-HCM`
- kho nguồn: `WH-DC`
- vendor: `NCC ABC`

Dòng hàng:

- `Burger`
- số lượng `20`
- `procurement_preference = purchase`
- `resolved_supply_method = purchase`

#### MER nội bộ

- `MER/2026/0003`
- trạng thái: `po_created`
- kho nhận: `WH-HCM`
- kho nguồn: `WH-DC`
- requesting partner: `Store`

Dòng hàng:

- `Eggs`
- số lượng `20`
- `procurement_preference = auto`
- `suggested_supply_method = internal`
- `resolved_supply_method = internal`
- `available_internal_qty = 1000`

### 1.6. Chứng từ mua ngoài đang có sẵn

Đã có 1 PO:

- `P00002`
- `origin = MER/2026/0001`
- vendor: `NCC ABC`
- trạng thái: `purchase`

PO line:

- `Burger`
- số lượng `20`

### 1.7. Chứng từ Supply Chain đang có sẵn

Đã có 2 allocation plan:

- `SCP/2026/0002`
  - trạng thái: `confirmed`
  - warehouse: `WH-DC`
  - liên kết `MER/2026/0003`
- `SCP/2026/0004`
  - trạng thái: `confirmed`
  - warehouse: `WH-DC`

Allocation line quan trọng:

#### `SCP/2026/0002`

- `Store`
- `Eggs`
- `demand_qty = 20`
- `suggested_qty = 20`
- `shortage_qty = 0`

### 1.8. User đã tạo sẵn để demo theo role

Đây là các tài khoản tôi đọc được trực tiếp từ DB:

- `admin` -> `Administrator`
- `mer` -> `Mer_NV`
- `mermer` -> `Mer_Manager`
- `ware` -> `Ware_NV`
- `wareware` -> `Ware_Mangement`
- `sup` -> `Supplier_NV`
- `SupplyChain` -> `SupplyChain`

Các group hiện có:

- `mer` có `MER Request User`
- `mermer` có `MER Request Manager`
- `ware` có `Receiving QC User`
- `wareware` có `Receiving QC Manager`
- `sup` có `Supplier Performance User`
- `SupplyChain` có `Supply Chain User`
- `admin` có đầy đủ manager group

Lưu ý:

- Tài liệu này chỉ ghi `login`
- mật khẩu là mật khẩu bạn đã tạo trước đó

## 2. Nguyên tắc demo đúng

Để người xem hiểu nhanh, bạn nên làm theo 2 bước:

1. mở dữ liệu có sẵn để giải thích
2. sau đó tạo mới một chứng từ tương tự

Đừng tạo mới ngay từ đầu nếu người xem chưa biết hệ thống đang chạy tới đâu.

## 3. App nên dùng sau khi bạn đã gom menu

Sau khi đã dọn menu, người dùng nên thao tác chủ yếu trong 4 app:

- `Mer`
- `Warehouse`
- `SupplyChain`
- `Supplier`

Trong đó:

- các menu chuẩn của `Mua hàng` đã nằm trong `Mer`
- các menu chuẩn của `Tồn kho` đã nằm trong `Warehouse`

## PHẦN A. LUỒNG 1: DEMO TOÀN BỘ BẰNG ADMIN

Phần này phù hợp khi bạn muốn:

- demo một mình
- vừa giải thích vừa thao tác
- không cần đổi tài khoản liên tục

## A1. Đăng nhập và kiểm tra app

### Bước 1

Đăng nhập bằng:

- `login`: `admin`

### Bước 2

Nhìn thanh app và xác nhận bạn thấy:

- `Mer`
- `Warehouse`
- `SupplyChain`
- `Supplier`

### Bước 3

Nếu thanh app bị ẩn:

- bấm biểu tượng mắt hoặc mắt gạch trên navbar để hiện lại

## A2. Đọc hiểu dữ liệu có sẵn trước khi tạo mới

Mục tiêu phần này là để người xem hiểu hệ thống đã có 2 flow thật đang tồn tại.

### A2.1. Mở MER mua ngoài đang có sẵn

### Bước 1

Vào:

`Mer -> MER Requests`

### Bước 2

Mở chứng từ:

- `MER/2026/0001`

### Bước 3

Giải thích cho người xem:

- đây là MER mua ngoài
- trạng thái hiện tại là đã tạo chứng từ cung ứng
- vendor là `NCC ABC`
- kho nhận là `WH-HCM`

### Bước 4

Xuống tab dòng hàng và chỉ rõ:

- sản phẩm là `Burger`
- số lượng `20`
- phương thức cung ứng là mua ngoài

### Bước 5

Bấm smart button:

- `Đơn mua`

### Bước 6

Mở PO:

- `P00002`

### Bước 7

Giải thích:

- PO này được sinh từ MER
- `origin = MER/2026/0001`
- vendor là `NCC ABC`

### Kết luận phần này

Người xem hiểu được:

`MER mua ngoài -> PO chuẩn của Odoo`

---

### A2.2. Mở MER nội bộ đang có sẵn

### Bước 1

Quay lại:

`Mer -> MER Requests`

### Bước 2

Mở chứng từ:

- `MER/2026/0003`

### Bước 3

Giải thích:

- đây là MER nội bộ
- kho nhận là `WH-HCM`
- kho nguồn là `WH-DC`
- cửa hàng yêu cầu là `Store`

### Bước 4

Ở dòng hàng, chỉ rõ:

- sản phẩm `Eggs`
- số lượng `20`
- `suggested_supply_method = internal`
- `resolved_supply_method = internal`
- `available_internal_qty = 1000`

### Bước 5

Bấm smart button:

- `Kế hoạch phân bổ`

### Bước 6

Mở:

- `SCP/2026/0002`

### Bước 7

Giải thích:

- plan này được sinh từ MER
- warehouse của plan là `WH-DC`
- có line phân bổ `Eggs`
- `demand = 20`
- `suggested = 20`
- `shortage = 0`

### Bước 8

Bấm smart button:

- `Điều chuyển`

### Bước 9

Mở internal transfer tương ứng, ví dụ:

- `WH-DC/INT/00002`

### Bước 10

Giải thích:

- nguồn là `WH-DC/Tồn kho`
- đích là `WH-HCM/Tồn kho`
- phiếu này sinh từ allocation plan
- allocation plan sinh từ MER nội bộ

### Kết luận phần này

Người xem hiểu được:

`MER nội bộ -> Allocation Plan -> Internal Transfer`

---

### A2.3. Mở KPI nhà cung cấp đang có sẵn

### Bước 1

Vào:

`Supplier -> Supplier Performance`

### Bước 2

Mở:

- `NCC ABC`

### Bước 3

Giải thích:

- supplier này có phát sinh PO từ MER mua ngoài
- KPI được đọc từ PO và receipt thật
- đây là báo cáo đầu ra, không nhập tay

### Bước 4

Bấm:

- `Đơn mua`
- `Phiếu nhập`

để cho người xem thấy chỉ số KPI có liên kết ngược về chứng từ.

## A3. Tạo mới lại luồng mua ngoài bằng admin

Sau khi người xem đã hiểu MER/0001, bạn tạo mới một chứng từ tương tự.

### A3.1. Tạo MER mới

### Bước 1

Vào:

`Mer -> MER Requests`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store`
- `Nhà cung cấp chính`: `NCC ABC`
- `Cho phép đáp ứng nội bộ`: có thể bật hoặc tắt

### Bước 4

Vào tab:

`Dòng hàng`

### Bước 5

Thêm 1 dòng:

- `Sản phẩm`: `Burger`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Mua ngoài`

### Bước 6

Kiểm tra:

- `Phương thức cung ứng áp dụng` phải là mua ngoài
- partner nên là `NCC ABC`

### Bước 7

Lưu lại.

## A3.2. Duyệt MER

### Bước 1

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`
- `Duyệt`

### Kết quả mong đợi

- trạng thái sang `Đã duyệt`

## A3.3. Tạo chứng từ cung ứng

### Bước 1

Nhấn:

- `Tạo chứng từ cung ứng`

### Kết quả mong đợi

- hệ thống sinh PO mới
- PO được confirm
- `origin` là mã MER vừa tạo

## A3.4. Mở receipt và QC

### Bước 1

Từ PO vừa sinh, mở receipt.

Nếu không mở từ PO, vào:

`Warehouse -> Operations -> Transfers`

hoặc:

`Warehouse -> Operations -> Receiving QC`

### Bước 2

Mở phiếu nhập mới nhất.

### Bước 3

Vào tab:

`Kiểm tra chất lượng nhập kho`

### Bước 4

Nhập số liệu:

- `Số lượng thực nhận = 20`
- `Số lượng hư hỏng = 1`

### Bước 5

Nhập ghi chú QC, ví dụ:

`1 sản phẩm bị lỗi bao bì`

### Bước 6

Nhấn:

- `Bắt đầu QC`
- `QC đạt`

### Bước 7

Validate phiếu nhập theo flow chuẩn Odoo.

## A3.5. Kiểm tra KPI supplier

### Bước 1

Vào:

`Supplier -> Supplier Performance`

### Bước 2

Mở:

- `NCC ABC`

### Bước 3

Giải thích:

- số `Đơn mua` tăng
- số `Phiếu nhập` tăng
- `Điểm chất lượng` bị ảnh hưởng bởi số hư hỏng

## A4. Tạo mới lại luồng nội bộ bằng admin

Sau khi người xem đã hiểu `MER/2026/0003`, bạn tạo mới một chứng từ tương tự.

## A4.1. Kiểm tra tồn trước khi tạo

### Bước 1

Vào:

`Warehouse -> Products`

### Bước 2

Mở sản phẩm:

- `Eggs`

### Bước 3

Kiểm tra tồn tại:

- `WH-DC/Tồn kho`

Nếu cần nhập tồn thêm:

- vào forecast / update quantity
- nhập tồn đúng location `WH-DC/Tồn kho`

Không nhập nhầm vào:

- `WH/Stock`

vì MER nội bộ đang đọc tồn từ `WH-DC`.

## A4.2. Tạo MER nội bộ mới

### Bước 1

Vào:

`Mer -> MER Requests`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store`
- bật `Cho phép đáp ứng nội bộ`

### Bước 4

Thêm dòng:

- `Sản phẩm`: `Eggs`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Tự động`

### Bước 5

Kiểm tra:

- `Số lượng nội bộ khả dụng` phải lớn hơn 0
- `Phương thức cung ứng đề xuất` là nội bộ
- `Phương thức cung ứng áp dụng` là nội bộ

### Nếu `Số lượng nội bộ khả dụng = 0`

Nguyên nhân thường là:

- chưa nhập tồn vào `WH-DC/Tồn kho`
- chọn sai kho nguồn
- nhập tồn nhầm vào `WH/Stock` thay vì `WH-DC/Tồn kho`

### Bước 6

Lưu lại.

## A4.3. Duyệt và tạo chứng từ nội bộ

### Bước 1

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`
- `Duyệt`

### Bước 2

Nhấn:

- `Tạo chứng từ cung ứng`

### Kết quả mong đợi

- hệ thống tạo allocation plan
- hệ thống tạo internal transfer

## A4.4. Kiểm tra Allocation Plan

### Bước 1

Trên MER, bấm:

- `Kế hoạch phân bổ`

### Bước 2

Mở plan mới nhất.

### Bước 3

Kiểm tra line:

- `Sản phẩm = Eggs`
- `Nhu cầu = 20`
- `Số lượng đề xuất = 20`
- `Số lượng thiếu = 0`

## A4.5. Kiểm tra transfer nội bộ

### Bước 1

Trên plan, bấm:

- `Điều chuyển`

### Bước 2

Mở phiếu điều chuyển mới tạo.

### Bước 3

Kiểm tra:

- `Vị trí nguồn = WH-DC/Tồn kho`
- `Vị trí đích = WH-HCM/Tồn kho`
- trạng thái là `Sẵn sàng` hoặc tương đương

### Bước 4

Validate phiếu nếu muốn kết thúc đầy đủ vòng đời.

## PHẦN B. LUỒNG 2: DEMO THEO TỪNG ROLE, ĐĂNG NHẬP TỪNG TÀI KHOẢN

Phần này bám đúng user bạn đã tạo.

## B1. Danh sách login để dùng khi demo

### User admin

- `login`: `admin`
- vai trò: toàn quyền

### User Mer nhân viên

- `login`: `mer`
- tên hiển thị: `Mer_NV`
- group: `MER Request User`

### User Mer quản lý

- `login`: `mermer`
- tên hiển thị: `Mer_Manager`
- group: `MER Request Manager`

### User kho nhân viên

- `login`: `ware`
- tên hiển thị: `Ware_NV`
- group: `Receiving QC User`

### User kho quản lý

- `login`: `wareware`
- tên hiển thị: `Ware_Mangement`
- group: `Receiving QC Manager`

### User supplier

- `login`: `sup`
- tên hiển thị: `Supplier_NV`
- group: `Supplier Performance User`

### User supply chain

- `login`: `SupplyChain`
- tên hiển thị: `SupplyChain`
- group: `Supply Chain User`

## B2. Vai trò từng người trong buổi demo

Bạn nên chia như sau:

- `mer`: tạo MER
- `mermer`: duyệt MER và tạo chứng từ cung ứng
- `ware`: làm QC nhập kho
- `wareware`: dùng khi cần demo quyền quản lý kho hoặc reject QC
- `SupplyChain`: xem plan, tạo suggestion, xem transfer
- `sup`: xem KPI nhà cung cấp

## B3. Demo theo role với dữ liệu có sẵn trước

Trước khi tạo mới, mỗi user nên mở dữ liệu có sẵn để hiểu mình đang phụ trách phần nào.

### B3.1. Mer user đọc chứng từ cũ

Đăng nhập:

- `mer`

Vào:

`Mer -> MER Requests`

Mở:

- `MER/2026/0001`
- `MER/2026/0003`

Mer user cần hiểu:

- MER/0001 là flow mua ngoài
- MER/0003 là flow nội bộ

### B3.2. Mer manager đọc chứng từ cũ

Đăng nhập:

- `mermer`

Vào `Mer -> MER Requests`

Mở cùng 2 chứng từ trên và chỉ cho người xem:

- manager là người bấm `Duyệt`
- manager là người bấm `Tạo chứng từ cung ứng`

### B3.3. Warehouse user đọc receipt cũ

Đăng nhập:

- `ware`

Vào:

`Warehouse -> Operations -> Receiving QC`

Tìm phiếu nhập từ `MER/2026/0001` nếu đã có.

Warehouse user cần hiểu:

- phần của mình bắt đầu sau khi PO sinh receipt
- kho chịu trách nhiệm QC

### B3.4. SupplyChain user đọc allocation plan cũ

Đăng nhập:

- `SupplyChain`

Vào:

`SupplyChain -> Allocation Plans`

Mở:

- `SCP/2026/0002`

SupplyChain user cần hiểu:

- đây là plan nội bộ sinh từ MER
- line `Eggs` có nhu cầu `20`, đề xuất `20`

### B3.5. Supplier user đọc KPI cũ

Đăng nhập:

- `sup`

Vào:

`Supplier -> Supplier Performance`

Mở:

- `NCC ABC`

Supplier user cần hiểu:

- KPI là kết quả cuối cùng
- dữ liệu lấy từ PO và receipt thật

## B4. Tạo mới flow mua ngoài theo role

## B4.1. Mer user tạo yêu cầu

Đăng nhập:

- `mer`

Vào:

`Mer -> MER Requests`

Nhấn `Mới`

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store`
- `Nhà cung cấp chính`: `NCC ABC`

Thêm dòng:

- `Sản phẩm`: `Burger`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Mua ngoài`

Lưu lại.

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`

Sau đó logout.

## B4.2. Mer manager duyệt và tạo PO

Đăng nhập:

- `mermer`

Vào:

`Mer -> MER Requests`

Mở chứng từ Mer vừa tạo.

Nhấn:

- `Duyệt`
- `Tạo chứng từ cung ứng`

Kết quả:

- hệ thống sinh PO
- PO confirm

Manager giải thích:

- đây là điểm ra quyết định mua ngoài

Sau đó logout.

## B4.3. Warehouse user nhận hàng và QC

Đăng nhập:

- `ware`

Vào:

`Warehouse -> Operations -> Receiving QC`

Mở phiếu nhập mới sinh.

Vào tab:

- `Kiểm tra chất lượng nhập kho`

Nhập:

- `Số lượng thực nhận = 20`
- `Số lượng hư hỏng = 1`

Nhấn:

- `Bắt đầu QC`
- `QC đạt`

Validate phiếu nhập.

Sau đó logout.

## B4.4. Supplier user xem KPI

Đăng nhập:

- `sup`

Vào:

`Supplier -> Supplier Performance`

Mở:

- `NCC ABC`

Kiểm tra:

- `Đơn mua`
- `Phiếu nhập`
- `Tỷ lệ giao đúng hạn`
- `Độ chính xác giao hàng`
- `Điểm chất lượng`

Khi demo, nhấn thêm:

- `Đơn mua`
- `Phiếu nhập`

để chứng minh KPI đọc từ dữ liệu thật.

## B5. Tạo mới flow nội bộ theo role

## B5.1. Mer user tạo MER nội bộ

Đăng nhập:

- `mer`

Vào:

`Mer -> MER Requests`

Nhấn `Mới`

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store`
- bật `Cho phép đáp ứng nội bộ`

Thêm dòng:

- `Sản phẩm`: `Eggs`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Tự động`

Trước khi lưu, kiểm tra:

- `Số lượng nội bộ khả dụng > 0`
- `Phương thức cung ứng áp dụng = nội bộ`

Lưu lại.

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`

Logout.

## B5.2. Mer manager duyệt và tạo allocation plan

Đăng nhập:

- `mermer`

Mở MER vừa tạo.

Nhấn:

- `Duyệt`
- `Tạo chứng từ cung ứng`

Kết quả:

- sinh allocation plan
- sinh internal transfer

Logout.

## B5.3. SupplyChain user kiểm tra kế hoạch phân bổ

Đăng nhập:

- `SupplyChain`

Vào:

`SupplyChain -> Allocation Plans`

Mở plan mới sinh.

Kiểm tra:

- warehouse là `WH-DC`
- line `Eggs`
- `Nhu cầu = 20`
- `Số lượng đề xuất = 20`
- `Số lượng thiếu = 0`

Nếu plan được tạo thủ công thay vì từ MER, user này còn có thể:

- bấm `Tạo đề xuất`
- bấm `Tạo điều chuyển`

Trong flow MER hiện tại, nhiều trường hợp plan và transfer đã được sinh sẵn.

Logout.

## B5.4. Warehouse user hoặc warehouse manager xử lý transfer

Đăng nhập:

- `ware`

hoặc:

- `wareware`

Vào:

`Warehouse -> Operations -> Transfers`

Mở phiếu điều chuyển nội bộ mới tạo.

Kiểm tra:

- nguồn `WH-DC/Tồn kho`
- đích `WH-HCM/Tồn kho`

Validate phiếu nếu muốn kết thúc đủ vòng đời.

## 4. Cách dùng dữ liệu cũ để giải thích dữ liệu mới

Khi người xem bị rối, bạn dùng quy tắc này:

### Nếu đang tạo MER mua ngoài mới

Nói:

`Chứng từ mới này làm giống MER/2026/0001`

Rồi mở `MER/2026/0001` để đối chiếu:

- cùng sản phẩm `Burger`
- cùng vendor `NCC ABC`
- cùng logic sinh PO

### Nếu đang tạo MER nội bộ mới

Nói:

`Chứng từ mới này làm giống MER/2026/0003`

Rồi mở `MER/2026/0003` để đối chiếu:

- cùng sản phẩm `Eggs`
- cùng kho nguồn `WH-DC`
- cùng logic sinh allocation plan

### Nếu đang giải thích supplier KPI

Nói:

`KPI của NCC ABC đang lấy từ PO P00002 và các receipt liên quan`

## 5. Các lỗi rất hay gặp khi demo và cách xử lý ngay

## 5.1. `Available Internal Qty = 0`

Kiểm tra:

- có chọn đúng `Kho nguồn = WH-DC` không
- tồn có nằm ở đúng `WH-DC/Tồn kho` không
- có nhập nhầm vào `WH/Stock` không

## 5.2. Supplier Performance trống

Kiểm tra:

- đã upgrade `supplier_management` chưa
- supplier có phát sinh PO hoặc receipt chưa

## 5.3. Không tạo được internal transfer

Kiểm tra:

- MER đã `Duyệt` chưa
- `Kho nguồn` khác `Kho nhận` chưa
- có tồn trong `WH-DC/Tồn kho` chưa

## 5.4. Không pass QC được

Kiểm tra:

- đã nhập `Số lượng thực nhận` chưa
- đã bấm `Bắt đầu QC` chưa

## 6. Kịch bản nói ngắn gọn khi demo

Bạn có thể nói đúng 4 câu này:

1. `Hệ thống có 2 luồng chính: mua ngoài và cấp nội bộ`
2. `MER là đầu vào, sau đó hệ thống quyết định sinh PO hoặc Allocation Plan`
3. `Kho xử lý receipt và QC, không phải bộ phận Mer`
4. `Supplier KPI là đầu ra cuối cùng, đọc từ PO và receipt thật`

## 7. Thứ tự demo đẹp nhất

Nếu bạn muốn demo mượt và ít bị rối, làm theo thứ tự này:

1. mở `MER/2026/0001`
2. mở `P00002`
3. mở KPI `NCC ABC`
4. mở `MER/2026/0003`
5. mở `SCP/2026/0002`
6. mở transfer nội bộ
7. tạo mới MER mua ngoài
8. chạy hết flow mua ngoài
9. tạo mới MER nội bộ
10. chạy hết flow nội bộ