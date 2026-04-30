# Tổng hợp chức năng hệ thống MIS Purchasing Odoo

Tài liệu này tổng hợp các chức năng chính đang được triển khai trong thư mục `custom_addons`. Hệ thống tập trung vào quy trình mua hàng, quản lý Merchandise, vận hành cửa hàng và kiểm soát nhập kho/QC.

## 1. Merchandise Management

Module `merchandise_management` quản lý nghiệp vụ trung tâm của bộ phận Merchandise.

### Quản lý sản phẩm Merchandise

- Bổ sung thông tin nghiệp vụ cho sản phẩm:
  - Dừng đặt hàng đối với sản phẩm có vấn đề.
  - Trạng thái tồn kho: bình thường, thừa hàng, thiếu hàng, hàng tồn lâu.
  - Luồng cung ứng: lấy từ Kho tổng hoặc giao trực tiếp từ nhà cung cấp.
  - Vòng đời SKU: hàng mới, đang kinh doanh, bán chậm, xả hàng, ngừng kinh doanh.
  - Phân loại ABC theo mức độ quan trọng.
  - Cấu hình số ngày cảnh báo hàng cận hạn và mức giảm giá mặc định.
- Lưu giá khuyến mãi hiện tại và dòng khuyến mãi đang áp dụng cho từng sản phẩm/biến thể.

### Quản lý yêu cầu mua hàng PR

- Tạo phiếu yêu cầu mua hàng `mer.purchase.request` kèm nhiều dòng sản phẩm.
- Tự sinh mã PR bằng sequence.
- Theo dõi trạng thái PR:
  - Nháp.
  - Đã gửi.
  - Chờ quản lý duyệt.
  - Được phê duyệt.
  - Đã tạo PO/đang thực hiện.
  - Hoàn tất.
  - Từ chối.
  - Hủy.
- Tính tổng tiền dự kiến theo số lượng và đơn giá từng dòng.
- Tự lấy đơn giá từ nhà cung cấp nếu sản phẩm có bảng giá NCC, nếu không thì dùng giá vốn.
- Kiểm tra điều khoản thanh toán trước khi trình quản lý duyệt.
- Kiểm tra ngân sách theo ngành hàng trước khi phê duyệt.
- Chặn tạo PO nếu sản phẩm đang bật trạng thái dừng đặt hàng.
- Tạo PO từ PR đã duyệt và tự động xác nhận PO.
- Theo dõi số PO liên quan và mở danh sách PO từ PR.
- Gửi thông báo qua chatter cho bên liên quan sau khi tạo PO.

### Quản lý ngân sách mua hàng

- Tạo ngân sách mua hàng theo ngành hàng và khoảng thời gian.
- Theo dõi:
  - Tổng ngân sách.
  - Số tiền đã sử dụng từ các PO đã duyệt/hoàn tất.
  - Số tiền còn lại.
- Trạng thái ngân sách gồm nháp, đang áp dụng và đã đóng.
- Hiển thị cảnh báo ngân sách trực tiếp trên PR.
- Chặn phê duyệt PR khi vượt ngân sách còn lại.

### Quản lý khuyến mãi

- Tạo chương trình khuyến mãi với mã tự sinh, thời gian áp dụng và danh sách cửa hàng/kho áp dụng.
- Khai báo nhiều dòng sản phẩm, phần trăm giảm giá, số lượng khuyến mãi tối đa, số lượng đã bán và số lượng còn lại.
- Tính tồn kho của sản phẩm tại các cửa hàng áp dụng.
- Kích hoạt chương trình sau khi kiểm tra đủ thông tin: tên, mã, sản phẩm, mức giảm, cửa hàng áp dụng và ngày kết thúc.
- Khi kích hoạt, hệ thống cập nhật giá khuyến mãi hiện tại trên sản phẩm.
- Nếu nhiều khuyến mãi cùng áp dụng cho một sản phẩm, hệ thống chọn giá khuyến mãi tốt nhất.
- Cho phép kết thúc chương trình và reset giá khuyến mãi.
- Không cho xóa chương trình đang chạy.
- Có scheduler tự động:
  - Chuyển khuyến mãi quá hạn sang hết hạn.
  - Quét hàng cận hạn tại cửa hàng.
  - Tạo chương trình khuyến mãi hàng cận hạn.
  - Cập nhật lại giá khuyến mãi sản phẩm.
- Có thao tác quét thủ công hàng cận hạn từ giao diện.

### Quản lý sai lệch hàng hóa

- Tạo báo cáo sai lệch `mer.discrepancy.report` cho các trường hợp:
  - Hàng dư.
  - Hàng thiếu.
  - Hàng lỗi.
- Tự tính chênh lệch giữa số lượng chứng từ và số lượng thực nhận.
- Tự gợi ý lý do sai lệch dựa trên số lượng thực tế.
- Kiểm tra tính hợp lệ giữa số lượng và lý do sai lệch.
- Với hàng thiếu, có thể tạo PO bù hoặc PR bù hàng.
- Với hàng dư, có thể tạo phiếu thu hồi hàng.
- Với hàng lỗi, có thể tạo PR bù hàng.
- Ghi nhận phương án xử lý và liên kết PO/PR/phiếu kho phát sinh.

### Dashboard Merchandise

- Cung cấp dữ liệu dashboard cho bộ phận Merchandise:
  - Số PR nháp, đang chờ xử lý, đang thực hiện, hoàn tất, bị từ chối.
  - Số phiếu QC bị từ chối.
  - Ngân sách đã dùng và tổng ngân sách.
  - Số mặt hàng cần bổ sung.
  - Số SKU mới và SKU chuẩn bị xả/ngừng.
- Hiển thị pipeline PR gần đây và hoạt động chatter mới nhất.

### Đánh giá nhà cung cấp

- Mở rộng đối tác/NCC với các chỉ số:
  - Tổng số PO.
  - Số lần sai lệch.
  - Điểm uy tín.
  - Xếp hạng: xuất sắc, tốt, trung bình, cần theo dõi.

## 2. Store Management

Module `store_management` quản lý cửa hàng, tồn kho tại cửa hàng, bán hàng và luồng yêu cầu bổ sung hàng.

### Quản lý cửa hàng

- Tạo danh mục cửa hàng `store.store` gồm mã, tên, người phụ trách, mức ưu tiên, thông tin liên hệ và địa chỉ.
- Khi tạo cửa hàng, hệ thống tự tạo:
  - Đối tác tương ứng của cửa hàng.
  - Kho tương ứng của cửa hàng.
- Chuẩn hóa mã cửa hàng, giới hạn mã theo chữ/số in hoa.
- Đồng bộ thông tin cửa hàng sang partner và warehouse.
- Không cho xóa cửa hàng đã có PR, chỉ nên lưu trữ.
- Có thao tác liên kết lại warehouse nếu cấu hình sai.
- Theo dõi các chỉ số:
  - Số mặt hàng.
  - Số mặt hàng cần bổ sung.
  - Số PR.
  - Số đơn bán.
  - Doanh thu, lợi nhuận gộp và biên lợi nhuận.

### Định mức sản phẩm theo cửa hàng

- Quản lý danh sách sản phẩm được bán/tồn tại từng cửa hàng.
- Thiết lập tồn tối thiểu và tồn tối đa.
- Tính toán:
  - Tồn hiện tại.
  - Tồn khả dụng.
  - Số lượng đang chờ bổ sung.
  - Số lượng đề xuất bổ sung.
  - Tốc độ bán 30 ngày.
  - Số ngày tồn kho còn lại.
  - Cờ cần bổ sung hàng.
- Tạo PR bổ sung hàng tự động từ các dòng sản phẩm thiếu so với định mức.
- Chặn tạo PR trùng khi cửa hàng đã có PR đang xử lý cho cùng sản phẩm.

### Bán hàng tại cửa hàng

- Mở rộng `sale.order` với thông tin cửa hàng bán.
- Khi chọn cửa hàng, tự gán warehouse tương ứng.
- Lọc sản phẩm bán theo danh mục sản phẩm đang active và còn tồn khả dụng tại cửa hàng.
- Dòng bán hàng cũng chỉ hiển thị các sản phẩm có sẵn theo cửa hàng đã chọn.

### Mở rộng quy trình PR cho cửa hàng

- Bổ sung `store_id` vào PR để xác định cửa hàng yêu cầu.
- Bổ sung số lượng được duyệt cho từng dòng PR.
- Cho phép Merchandise chọn phương án đáp ứng:
  - Kho tổng có sẵn.
  - Nhà cung cấp giao về Kho tổng.
  - Nhà cung cấp giao thẳng cửa hàng.
- Tính tồn Kho tổng, tồn khả dụng, tồn các kho khác và giá trị tồn.
- Theo dõi trạng thái hậu cần của từng dòng:
  - Không áp dụng.
  - Chờ Kho tổng kiểm.
  - Chờ NCC giao Kho tổng.
  - Chưa đủ hàng.
  - Chờ Kho tổng giao.
  - Hàng lỗi.
  - Đã giao cửa hàng.
- Kho tổng có thể xác nhận đủ hàng hoặc thiếu hàng trước khi giao.
- Tạo phiếu điều chuyển nội bộ từ Kho tổng về cửa hàng.
- Tạo PO theo từng nhà cung cấp và phương án đáp ứng.
- Tự đồng bộ trạng thái PR theo tiến độ PO/phiếu kho.
- Tự tạo hóa đơn NCC khi PO đã đủ điều kiện.

### Nhận hàng và xử lý sai lệch tại cửa hàng

- Xác định nguồn hàng của phiếu nhận:
  - NCC giao về Kho tổng.
  - NCC giao thẳng cửa hàng.
  - Kho tổng giao về cửa hàng.
- Cửa hàng kiểm tra số lượng thực nhận trước khi QC.
- Ghi nhận các tình huống:
  - Không sai lệch.
  - Nhận thiếu.
  - Nhận dư.
  - Vừa thiếu vừa dư.
  - Từ chối lô do hàng lỗi.
- Với hàng thiếu, cửa hàng gửi báo cáo cho Merchandise để tạo PR bù.
- Với hàng dư, hệ thống tạo báo cáo nhận dư `mer.excess.receipt`, điều chỉnh vị trí hàng dư chờ thu hồi và tạo phiếu thu hồi về Kho tổng.
- Với hàng lỗi, hệ thống tạo báo cáo sai lệch và xử lý trả/thu hồi theo luồng kho.
- Có wizard hỗ trợ tạo báo cáo sai lệch từ phiếu kho.

### Quyền và menu cửa hàng

- Có nhóm quyền Store User và Store Manager.
- Cấu hình record rule để người dùng cửa hàng chỉ nhìn thấy dữ liệu kho/cửa hàng phù hợp.
- Từ menu cửa hàng, người dùng chủ yếu được tạo PR, gửi PR và theo dõi trạng thái xử lý.

## 3. Warehouse Management

Module `warehouse_management` quản lý kiểm tra QC đầu vào, trạng thái nhận hàng và tích hợp menu kho.

### QC phiếu nhập kho

- Mở rộng `stock.picking` với trạng thái QC:
  - Nháp.
  - Đang kiểm tra.
  - Đạt.
  - Hàng lỗi.
- Ghi nhận người kiểm QC, thời gian kiểm, ghi chú QC.
- Tính tổng:
  - Số lượng dự kiến.
  - Số lượng thực nhận.
  - Số lượng hư hỏng.
  - Số lượng chênh lệch.
  - Có sai lệch hay không.
- Chỉ cho thao tác QC trên phiếu nhập phù hợp.
- Chặn validate phiếu nhập nếu QC chưa đạt.
- Khi QC đạt:
  - Tự validate phiếu nhập.
  - Tự tạo hóa đơn NCC nếu PO đến trạng thái cần lập hóa đơn.
  - Tự khóa/hoàn tất PO khi các phiếu nhập liên quan đã xong.
- Khi QC không đạt:
  - Nếu phiếu chưa nhập kho, hủy phiếu để không làm thay đổi tồn kho.
  - Nếu đã nhập kho từ NCC, tạo phiếu trả hàng về NCC.
  - Nếu là điều chuyển nội bộ, tạo phiếu hoàn trả về kho nguồn.

### QC theo dòng hàng

- Mở rộng `stock.move` với:
  - Số lượng hư hỏng.
  - Ghi chú lỗi.
  - Chênh lệch theo dòng.
- Kiểm tra số lượng hư hỏng không được vượt quá số lượng thực nhận.

### Theo dõi PO và phiếu nhận

- Liên kết PO/phiếu kho với PR Merchandise.
- Tính trạng thái nhận hàng của PO:
  - Chưa nhận.
  - Đang nhận.
  - Đã nhận.
  - Có lỗi/sai lệch.
- Có thao tác hoàn tất/khóa PO.
- Bổ sung menu danh sách phiếu cần QC và tích hợp vào menu Merchandise/Kho.

### Tích hợp giao diện

- Có menu riêng cho Warehouse Management.
- Có nhóm quyền Receiving QC User và Receiving QC Manager.
- Có asset JS/XML/SCSS hỗ trợ chuyển đổi app/menu trong backend.

## 4. Luồng nghiệp vụ chính

### Luồng bổ sung hàng từ cửa hàng

1. Cửa hàng theo dõi định mức tồn kho từng sản phẩm.
2. Khi tồn thấp, hệ thống đề xuất số lượng cần bổ sung.
3. Cửa hàng tạo PR bổ sung hàng.
4. Merchandise kiểm tra, chọn phương án đáp ứng và trình duyệt.
5. Quản lý duyệt PR.
6. Hệ thống tạo PO hoặc phiếu điều chuyển tùy nguồn hàng.
7. Kho/NCC giao hàng.
8. Kho hoặc cửa hàng kiểm tra thực nhận và QC.
9. Nếu đạt, hàng được nhập kho và PR được cập nhật hoàn tất.
10. Nếu thiếu/dư/lỗi, hệ thống tạo báo cáo sai lệch để xử lý tiếp.

### Luồng NCC giao về Kho tổng rồi giao cửa hàng

1. Merchandise tạo/duyệt PR với phương án NCC giao về Kho tổng.
2. Hệ thống tạo PO cho NCC.
3. Kho tổng nhận hàng và QC.
4. Nếu QC đạt, hệ thống tạo phiếu giao Kho tổng -> Cửa hàng.
5. Cửa hàng nhận hàng, kiểm tra thực tế và QC.
6. Nếu có sai lệch, báo cáo được gửi cho Merchandise để bù hàng, thu hồi hàng dư hoặc xử lý hàng lỗi.

### Luồng NCC giao thẳng cửa hàng

1. PR được xử lý theo phương án NCC giao thẳng cửa hàng.
2. Hệ thống tạo PO giao về warehouse của cửa hàng.
3. Cửa hàng kiểm tra số lượng thực tế.
4. QC đạt thì nhập kho cửa hàng.
5. Sai lệch được ghi nhận thành báo cáo để Merchandise xử lý.

### Luồng xử lý hàng cận hạn

1. Scheduler hoặc người dùng quét tồn kho tại các cửa hàng.
2. Hệ thống tìm các lô hàng còn tồn và sắp hết hạn theo cấu hình từng sản phẩm.
3. Tạo hoặc cập nhật chương trình khuyến mãi hàng cận hạn.
4. Merchandise nhập mức giảm và kích hoạt chương trình.
5. Hệ thống cập nhật giá khuyến mãi trên sản phẩm.
6. Khi hết hạn chương trình, hệ thống chuyển trạng thái và cập nhật lại giá.

## 5. Phân quyền chính

- Merchandise User: thao tác các nghiệp vụ Merchandise cơ bản như PR, khuyến mãi, sai lệch, ngân sách.
- Merchandise Manager: duyệt/xử lý cấp quản lý cho nghiệp vụ Merchandise.
- Store User: tạo và theo dõi PR cửa hàng, xử lý nhận hàng trong phạm vi cửa hàng.
- Store Manager: xử lý các thao tác quản lý cửa hàng.
- Receiving QC User: thực hiện nghiệp vụ nhận hàng và QC kho.
- Receiving QC Manager: xử lý các thao tác QC cấp quản lý.

## 6. Các đối tượng dữ liệu quan trọng

- `mer.purchase.request`: phiếu yêu cầu mua hàng Merchandise.
- `mer.purchase.request.line`: dòng sản phẩm trong PR.
- `mer.purchase.budget`: ngân sách mua hàng theo ngành hàng.
- `mer.promotion`: chương trình khuyến mãi.
- `mer.promotion.line`: dòng sản phẩm khuyến mãi.
- `mer.discrepancy.report`: báo cáo sai lệch hàng hóa.
- `store.store`: cửa hàng.
- `store.product.line`: định mức sản phẩm theo cửa hàng.
- `mer.excess.receipt`: báo cáo nhận dư hàng tại cửa hàng.
- `stock.picking`: phiếu kho được mở rộng thêm QC, nguồn hàng và trạng thái giao nhận.
- `stock.move`: dòng phiếu kho được mở rộng thêm số lượng hư hỏng và ghi chú lỗi.
- `purchase.order`: PO được liên kết với PR và trạng thái nhận hàng.
