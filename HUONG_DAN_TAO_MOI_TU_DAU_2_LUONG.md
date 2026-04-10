# Hướng Dẫn Tạo Mới Từ Đầu, Step By Step, 2 Luồng Demo

Tài liệu này dành cho trường hợp:

- người dùng chưa biết dữ liệu hiện có là gì
- muốn làm lại từ đầu
- muốn có hướng dẫn thật chi tiết để tự dựng dữ liệu demo

Tài liệu gồm 2 luồng:

- Luồng 1: làm toàn bộ bằng `admin`
- Luồng 2: làm theo từng role, đăng nhập bằng nhiều tài khoản khác nhau

Mục tiêu cuối cùng là chạy được 2 flow nghiệp vụ:

1. `MER -> Duyệt -> Tạo PO -> Phiếu nhập -> QC -> KPI nhà cung cấp`
2. `MER -> Duyệt -> Tạo Allocation Plan -> Internal Transfer`

## 1. Những app bạn sẽ dùng

Sau khi hệ thống đã được dọn menu, bạn sẽ thao tác chủ yếu trong 4 app:

- `Mer`
- `Warehouse`
- `SupplyChain`
- `Supplier`

Ngoài ra có thể dùng thêm:

- `Liên hệ`
- `Cài đặt`

Lưu ý:

- menu chuẩn `Mua hàng` đã được đưa vào `Mer`
- menu chuẩn `Tồn kho` đã được đưa vào `Warehouse`

## 2. Điều kiện trước khi bắt đầu

Bạn cần kiểm tra trước:

1. Đã cài đủ 4 module custom:
   - `Warehouse Management`
   - `Supply Chain Management`
   - `Supplier Management`
   - `MER Simulation Request`
2. Có quyền vào:
   - `Cài đặt`
   - `Liên hệ`-> Cài module tên "Liên hệ"
   - `Mer`
   - `Warehouse`
   - `SupplyChain`
   - `Supplier`
3. Nếu thanh app đang bị ẩn:
   - bấm biểu tượng mắt hoặc mắt gạch trên navbar để hiện lại

## 3. Kết quả dữ liệu bạn sẽ tạo

Để dễ theo dõi, trong tài liệu này tôi dùng thống nhất bộ dữ liệu demo sau:

### Warehouse

- kho nguồn: `WH-DC`
- kho nhận: `WH-HCM`

### Partner

- nhà cung cấp: `NCC ABC`
- cửa hàng: `Store Q1`

### Product

- sản phẩm mua ngoài: `Burger`
- sản phẩm cấp nội bộ: `Eggs`

### Role user

- `admin`
- `mer`
- `mermer`
- `ware`
- `wareware`
- `sup`
- `SupplyChain`

Bạn có thể thay tên khác, nhưng nếu giữ đúng bộ tên này thì tài liệu sẽ dễ làm theo hơn.

## PHẦN A. LUỒNG 1: TẠO MỚI TỪ ĐẦU VÀ DEMO TOÀN BỘ BẰNG ADMIN

Phần này dành cho trường hợp bạn muốn:

- tự dựng toàn bộ dữ liệu một mình
- không đổi tài khoản liên tục
- làm nhanh để test hệ thống

## A1. Đăng nhập admin

### Bước 1

Mở Odoo.

### Bước 2

Đăng nhập bằng tài khoản:

- `admin`

### Bước 3

Xác nhận bạn thấy các app:

- `Mer`
- `Warehouse`
- `SupplyChain`
- `Supplier`
- `Liên hệ` -> Cài module tên "Liên hệ"
- `Cài đặt`

## A2. Tạo warehouse từ đầu

Phần này chỉ cần làm nếu hệ thống chưa có đủ 2 kho để demo.

### Bước 1

Vào:

`Warehouse -> Configuration -> Warehouse Management -> Warehouses`

### Bước 2

Kiểm tra xem đã có 2 kho này chưa:

- `WH-DC`
- `WH-HCM`

### Nếu chưa có

Tạo mới từng kho.

#### Tạo `WH-DC`

Nhấn `Mới` rồi nhập:

- `Tên kho`: `WH-DC`
- `Mã`: `WH-DC`

Lưu lại.

#### Tạo `WH-HCM`

Nhấn `Mới` rồi nhập:

- `Tên kho`: `WH-HCM`
- `Mã`: `WH-HC`

Lưu lại.

### Kết quả mong đợi

Bạn có:

- 1 kho nguồn là `WH-DC`
- 1 kho nhận là `WH-HCM`

## A3. Tạo nhà cung cấp từ đầu

### Bước 1

Vào:

`Liên hệ`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Tên`: `NCC ABC`

### Bước 4

Lưu lại.

### Kết quả mong đợi

Đã có một partner để dùng làm nhà cung cấp.

## A4. Tạo store partner từ đầu

### Bước 1

Vào:

`Liên hệ`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Tên`: `Store Q1`

### Bước 4

Lưu lại trước.

### Bước 5

Mở tab:

- `Chuỗi cung ứng`

### Bước 6

Nhập:

- `Là cửa hàng` = bật
- `Mức ưu tiên cửa hàng` = `Cao`

### Bước 7

Lưu lại.

### Kết quả mong đợi

`Store Q1` sẽ dùng trong:

- allocation rule
- MER internal

## A5. Tạo location của store

Phần này quan trọng với SupplyChain.

### Bước 1

Vào:

`Warehouse -> Configuration -> Locations`

### Bước 2

Nhấn `Mới`

### Bước 3

Tạo location:

- `Tên`: `Store Q1 Stock`
- `Parent Location`: chọn vùng thuộc kho `WH-HCM`
- `Location Type`: `Internal Location`

### Bước 4

Lưu lại.

### Kết quả mong đợi

Store đã có 1 location nội bộ để nhận hàng.

## A6. Tạo sản phẩm mua ngoài từ đầu

### Bước 1

Vào:

`Mer -> Products -> Products`

Nếu không thấy đúng menu này, bạn cũng có thể vào:

`Warehouse -> Products -> Products`

### Bước 2

Nhấn `Mới`

### Bước 3

Tạo sản phẩm:

- `Tên sản phẩm`: `Burger`
- loại: hàng hóa
- bật theo dõi tồn kho nếu màn hình có tùy chọn đó
- `UoM`: `Đơn vị`

### Bước 4

Mở tab:

- `Mua hàng`

### Bước 5

Thêm vendor:

- `NCC ABC`

### Bước 6

Lưu lại.

### Kết quả mong đợi

`Burger` sẽ được dùng cho flow mua ngoài.

## A7. Tạo sản phẩm nội bộ từ đầu

### Bước 1

Tạo tiếp sản phẩm mới:

- `Tên sản phẩm`: `Eggs`
- loại: hàng hóa
- bật theo dõi tồn kho
- `UoM`: `Đơn vị`

### Bước 2

Lưu lại.

### Kết quả mong đợi

`Eggs` sẽ được dùng cho flow cấp nội bộ.

## A8. Nhập tồn kho ban đầu cho `Eggs`

Đây là bước rất hay sai.

`Available Internal Qty` chỉ lên đúng khi hàng nằm trong đúng location của kho nguồn.

### Bước 1

Vào sản phẩm:

- `Eggs`

### Bước 2

Bấm smart button:

- `Hiện có`

hoặc:

- `Forecasted`

### Bước 3

Bấm:

- `Update Quantity`

### Bước 4

Nhấn `Mới`

### Bước 5

Nhập:

- `Product`: `Eggs`
- `Location`: `WH-DC/Tồn kho`
- `Counted`: `100`

### Bước 6

Lưu lại.

### Bước 7

Bấm:

- `Apply`
- hoặc `Apply All`

### Kết quả mong đợi

`Eggs` đã có tồn tại đúng location:

- `WH-DC/Tồn kho`

### Lưu ý cực quan trọng

Không nhập nhầm tồn vào:

- `WH/Stock`

nếu bạn định dùng `WH-DC` làm kho nguồn.

MER internal đọc tồn theo:

- `Source Warehouse`
- và location con của kho đó

## A9. Tạo allocation rule từ đầu

Phần này là dữ liệu nền của SupplyChain.

### Bước 1

Vào:

`SupplyChain -> Allocation Rules`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Cửa hàng`: `Store Q1`
- `Kho`: `WH-DC`
- `Vị trí cửa hàng`: `Store Q1 Stock`
- `Sản phẩm`: `Eggs`
- `Tồn tối thiểu`: `10`
- `Tồn tối đa`: `30`

### Bước 4

Lưu lại.

### Kết quả mong đợi

Rule này sẽ giúp:

- SupplyChain tự tính nhu cầu
- ưu tiên cấp hàng cho `Store Q1`

## A10. Tạo mới và chạy flow mua ngoài hoàn chỉnh bằng admin

## A10.1. Tạo MER mua ngoài

### Bước 1

Vào:

`Mer -> MER Requests`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập phần đầu:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store Q1`
- `Nhà cung cấp chính`: `NCC ABC`

### Bước 4

Vào tab:

- `Dòng hàng`

### Bước 5

Thêm 1 dòng:

- `Sản phẩm`: `Burger`
- `Số lượng`: `20`
- `Đơn vị tính`: để hệ thống tự điền
- `Ưu tiên cung ứng`: `Mua ngoài`

### Bước 6

Quan sát các cột:

- `Phương thức cung ứng đề xuất`
- `Phương thức cung ứng áp dụng`
- `Đối tác đề xuất`
- `Đối tác`

### Kết quả mong đợi

- phương thức áp dụng là mua ngoài
- đối tác là `NCC ABC`

### Bước 7

Lưu MER.

## A10.2. Gửi và duyệt MER

### Bước 1

Nhấn:

- `Gửi yêu cầu`

### Bước 2

Nhấn:

- `Trình duyệt`

### Bước 3

Nhấn:

- `Duyệt`

### Kết quả mong đợi

Trạng thái MER chuyển sang:

- `Đã duyệt`

## A10.3. Tạo PO từ MER

### Bước 1

Nhấn:

- `Tạo chứng từ cung ứng`

### Kết quả mong đợi

Hệ thống sẽ:

- tạo `Purchase Order`
- tự confirm PO
- gắn `origin = mã MER`

### Bước 2

Nếu hệ thống mở thẳng PO, kiểm tra:

- vendor là `NCC ABC`
- `origin` là mã MER

### Bước 3

Nếu không mở tự động, dùng smart button:

- `Đơn mua`

để mở.

## A10.4. Nhận hàng và QC

### Bước 1

Từ PO, mở receipt liên quan.

Hoặc vào:

`Warehouse -> Operations -> Receiving QC`

### Bước 2

Mở receipt mới.

### Bước 3

Vào tab:

- `Kiểm tra chất lượng nhập kho`

### Bước 4

Nhập:

- `Số lượng thực nhận = 20`
- `Số lượng hư hỏng = 1`

### Bước 5

Nhập ghi chú:

- `1 sản phẩm bị lỗi bao bì`

### Bước 6

Nhấn:

- `Bắt đầu QC`

### Bước 7

Nhấn:

- `QC đạt`

### Bước 8

Validate phiếu nhập theo flow chuẩn Odoo.

### Kết quả mong đợi

- phiếu nhập ở trạng thái hoàn tất
- đã ghi nhận QC

## A10.5. Xem KPI nhà cung cấp

### Bước 1

Vào:

`Supplier -> Supplier Performance`

### Bước 2

Mở:

- `NCC ABC`

### Bước 3

Kiểm tra:

- `Đơn mua`
- `Phiếu nhập`
- `Lead time trung bình`
- `Tỷ lệ giao đúng hạn`
- `Độ chính xác giao hàng`
- `Điểm chất lượng`

### Bước 4

Bấm thêm:

- `Đơn mua`
- `Phiếu nhập`

để xem liên kết ngược tới chứng từ thật.

## A11. Tạo mới và chạy flow nội bộ hoàn chỉnh bằng admin

## A11.1. Tạo MER nội bộ

### Bước 1

Vào:

`Mer -> MER Requests`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store Q1`
- bật `Cho phép đáp ứng nội bộ`

### Bước 4

Vào tab:

- `Dòng hàng`

### Bước 5

Thêm 1 dòng:

- `Sản phẩm`: `Eggs`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Tự động`

### Bước 6

Kiểm tra:

- `Số lượng nội bộ khả dụng > 0`
- `Phương thức cung ứng đề xuất = nội bộ`
- `Phương thức cung ứng áp dụng = nội bộ`

### Nếu `Số lượng nội bộ khả dụng = 0`

Quay lại phần nhập tồn và kiểm tra:

- đã nhập đúng `WH-DC/Tồn kho` chưa

### Bước 7

Lưu MER.

## A11.2. Gửi, duyệt, tạo chứng từ nội bộ

### Bước 1

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`
- `Duyệt`

### Bước 2

Nhấn:

- `Tạo chứng từ cung ứng`

### Kết quả mong đợi

Hệ thống sẽ:

- tạo allocation plan
- tạo internal transfer

## A11.3. Kiểm tra Allocation Plan

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

## A11.4. Kiểm tra internal transfer

### Bước 1

Trên allocation plan, bấm:

- `Điều chuyển`

### Bước 2

Mở phiếu điều chuyển mới nhất.

### Bước 3

Kiểm tra:

- `Vị trí nguồn = WH-DC/Tồn kho`
- `Vị trí đích = WH-HCM/Tồn kho`

### Bước 4

Validate phiếu để kết thúc flow nếu muốn.

## A12. Tạo plan thủ công trong SupplyChain, không qua MER

Phần này để test riêng module SupplyChain.

### Bước 1

Vào:

`SupplyChain -> Allocation Plans`

### Bước 2

Nhấn `Mới`

### Bước 3

Nhập:

- `Kho`: `WH-DC`
- `Vị trí nguồn`: `WH-DC/Tồn kho`
- `Loại điều chuyển`: loại internal của `WH-DC`
- `Bộ lọc sản phẩm`: `Eggs`

### Bước 4

Lưu lại.

### Bước 5

Nhấn:

- `Tạo đề xuất`

### Bước 6

Kiểm tra trong tab `Dòng phân bổ`:

- có line của `Eggs`
- có cửa hàng `Store Q1`

### Bước 7

Nhấn:

- `Tạo điều chuyển`

### Kết quả mong đợi

- tạo transfer nội bộ
- plan chuyển trạng thái

## PHẦN B. LUỒNG 2: TẠO MỚI TỪ ĐẦU THEO TỪNG ROLE ĐĂNG NHẬP RIÊNG

Phần này phù hợp khi bạn muốn mô phỏng đúng nghiệp vụ thực tế.

## B1. Tạo các user role từ đầu

Nếu user chưa có, tạo theo đúng bộ sau.

### Bước 1

Đăng nhập `admin`

Vào:

`Cài đặt -> Người dùng & Công ty -> Người dùng`

### Bước 2

Tạo user `mer`

Nhập:

- `Tên`: `Mer_NV`
- `Login`: `mer`

Gán quyền:

- `MER Request User`

### Bước 3

Tạo user `mermer`

Nhập:

- `Tên`: `Mer_Manager`
- `Login`: `mermer`

Gán quyền:

- `MER Request Manager`

### Bước 4

Tạo user `ware`

Nhập:

- `Tên`: `Ware_NV`
- `Login`: `ware`

Gán quyền:

- `Receiving QC User`

### Bước 5

Tạo user `wareware`

Nhập:

- `Tên`: `Ware_Mangement`
- `Login`: `wareware`

Gán quyền:

- `Receiving QC Manager`

### Bước 6

Tạo user `sup`

Nhập:

- `Tên`: `Supplier_NV`
- `Login`: `sup`

Gán quyền:

- `Supplier Performance User`

### Bước 7

Tạo user `SupplyChain`

Nhập:

- `Tên`: `SupplyChain`
- `Login`: `SupplyChain`

Gán quyền:

- `Supply Chain User`

### Bước 8

Đặt mật khẩu cho từng user theo cách bạn đang dùng trong hệ thống.

## B2. Tạo dữ liệu nền vẫn phải làm bằng admin trước

Trước khi demo role-based, bạn vẫn nên dùng `admin` để tạo trước:

- warehouse
- supplier
- store
- location
- product
- tồn kho
- allocation rule

Bạn làm đúng từ:

- phần `A2` đến `A9`

sau đó mới chuyển sang đăng nhập từng người.

## B3. Luồng role-based cho mua ngoài

## B3.1. Mer user tạo MER

### Bước 1

Logout khỏi `admin`

### Bước 2

Đăng nhập:

- `login = mer`

### Bước 3

Vào:

`Mer -> MER Requests`

### Bước 4

Nhấn `Mới`

### Bước 5

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store Q1`
- `Nhà cung cấp chính`: `NCC ABC`

### Bước 6

Thêm dòng:

- `Sản phẩm`: `Burger`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Mua ngoài`

### Bước 7

Lưu lại.

### Bước 8

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`

### Kết quả mong đợi

MER đang ở trạng thái:

- `Chờ duyệt`

### Bước 9

Logout.

## B3.2. Mer manager duyệt và tạo PO

### Bước 1

Login:

- `mermer`

### Bước 2

Vào:

`Mer -> MER Requests`

### Bước 3

Mở MER vừa tạo.

### Bước 4

Nhấn:

- `Duyệt`

### Bước 5

Nhấn:

- `Tạo chứng từ cung ứng`

### Kết quả mong đợi

- hệ thống tạo PO
- PO confirm

### Bước 6

Logout.

## B3.3. Warehouse user làm receipt và QC

### Bước 1

Login:

- `ware`

### Bước 2

Vào:

`Warehouse -> Operations -> Receiving QC`

### Bước 3

Mở phiếu nhập mới nhất.

### Bước 4

Nhập:

- `Số lượng thực nhận = 20`
- `Số lượng hư hỏng = 1`

### Bước 5

Nhấn:

- `Bắt đầu QC`
- `QC đạt`

### Bước 6

Validate receipt.

### Bước 7

Logout.

## B3.4. Supplier user xem KPI

### Bước 1

Login:

- `sup`

### Bước 2

Vào:

`Supplier -> Supplier Performance`

### Bước 3

Mở:

- `NCC ABC`

### Bước 4

Xem:

- `Đơn mua`
- `Phiếu nhập`
- các chỉ số KPI

### Bước 5

Logout.

## B4. Luồng role-based cho nội bộ

## B4.1. Mer user tạo MER nội bộ

### Bước 1

Login:

- `mer`

### Bước 2

Vào:

`Mer -> MER Requests`

### Bước 3

Nhấn `Mới`

### Bước 4

Nhập:

- `Kho nhận`: `WH-HCM`
- `Kho nguồn`: `WH-DC`
- `Cửa hàng/đối tác yêu cầu`: `Store Q1`
- bật `Cho phép đáp ứng nội bộ`

### Bước 5

Thêm dòng:

- `Sản phẩm`: `Eggs`
- `Số lượng`: `20`
- `Ưu tiên cung ứng`: `Tự động`

### Bước 6

Kiểm tra:

- `Số lượng nội bộ khả dụng > 0`
- phương thức áp dụng là nội bộ

### Bước 7

Lưu lại.

### Bước 8

Nhấn:

- `Gửi yêu cầu`
- `Trình duyệt`

### Bước 9

Logout.

## B4.2. Mer manager duyệt và tạo allocation plan

### Bước 1

Login:

- `mermer`

### Bước 2

Mở MER vừa tạo.

### Bước 3

Nhấn:

- `Duyệt`
- `Tạo chứng từ cung ứng`

### Kết quả mong đợi

- sinh allocation plan
- sinh internal transfer

### Bước 4

Logout.

## B4.3. SupplyChain user kiểm tra kế hoạch phân bổ

### Bước 1

Login:

- `SupplyChain`

### Bước 2

Vào:

`SupplyChain -> Allocation Plans`

### Bước 3

Mở plan mới nhất.

### Bước 4

Kiểm tra:

- warehouse là `WH-DC`
- sản phẩm là `Eggs`
- số lượng đề xuất đúng với nhu cầu

### Bước 5

Nếu cần demo riêng SupplyChain, tạo thêm một plan thủ công theo phần `A12`.

### Bước 6

Logout.

## B4.4. Warehouse user hoặc warehouse manager xử lý transfer

### Bước 1

Login:

- `ware`

hoặc:

- `wareware`

### Bước 2

Vào:

`Warehouse -> Operations -> Transfers`

### Bước 3

Mở phiếu điều chuyển mới nhất.

### Bước 4

Kiểm tra:

- nguồn là `WH-DC/Tồn kho`
- đích là `WH-HCM/Tồn kho`

### Bước 5

Validate phiếu.

## B5. Nếu muốn role rõ hơn nữa

Bạn có thể thêm 1 user mua hàng riêng, nhưng với hệ thống hiện tại không bắt buộc, vì:

- `mermer` đã đủ để duyệt và tạo chứng từ cung ứng

## 4. Checklist nhanh để biết mình làm đúng hay chưa

### Với luồng mua ngoài

Bạn làm đúng khi thấy:

- MER ở trạng thái đã tạo chứng từ cung ứng
- có PO liên kết
- PO có `origin = mã MER`
- có receipt liên kết
- receipt đã QC
- supplier có KPI

### Với luồng nội bộ

Bạn làm đúng khi thấy:

- MER ở trạng thái đã tạo chứng từ cung ứng
- có allocation plan liên kết
- allocation plan có line
- có internal transfer
- transfer lấy hàng từ `WH-DC`
- transfer giao về `WH-HCM`

## 5. Những lỗi hay gặp khi bắt đầu từ số 0

## 5.1. Không thấy app custom

Kiểm tra:

- module đã cài chưa
- user có group chưa
- navbar app có đang bị ẩn không

## 5.2. `Available Internal Qty = 0`

Kiểm tra:

- có tồn ở đúng `WH-DC/Tồn kho` chưa
- có chọn `Kho nguồn = WH-DC` chưa
- có nhập nhầm tồn vào `WH/Stock` không

## 5.3. Không tạo được allocation line

Kiểm tra:

- đã tạo `Allocation Rule` chưa
- rule có đúng warehouse không
- product filter có đúng sản phẩm không

## 5.4. `Supplier Performance` trống

Kiểm tra:

- đã có PO confirm chưa
- đã có receipt done chưa
- đã upgrade module mới chưa

## 5.5. Không pass QC được

Kiểm tra:

- đã nhập số lượng thực nhận chưa
- đã bấm `Bắt đầu QC` chưa

## 6. Tài liệu nên đọc cùng

- [HUONG_DAN_STEP_BY_STEP_END_TO_END.md](/d:/DOHOANGPHUC/UTH/DoAnThucTe/MisOdooProject_HuggingFace/Mis_Purchasing_OdooProject/HUONG_DAN_STEP_BY_STEP_END_TO_END.md)
- [HUONG_DAN_CUC_CHI_TIET_ADMIN_VA_PHAN_QUYEN.md](/d:/DOHOANGPHUC/UTH/DoAnThucTe/MisOdooProject_HuggingFace/Mis_Purchasing_OdooProject/HUONG_DAN_CUC_CHI_TIET_ADMIN_VA_PHAN_QUYEN.md)
- [HUONG_DAN_DEMO_THEO_DU_LIEU_SAN_CO.md](/d:/DOHOANGPHUC/UTH/DoAnThucTe/MisOdooProject_HuggingFace/Mis_Purchasing_OdooProject/HUONG_DAN_DEMO_THEO_DU_LIEU_SAN_CO.md)

Nếu muốn, bước tiếp theo tôi có thể viết thêm:

- `CHECKLIST_TAO_DU_LIEU_TU_DAU.md`
- `SCRIPT_NOI_KHI_DEMO.md`
- `BAN_RUT_GON_1_TRANG_A4.md`
