---
title: MIS Odoo Project
emoji: 🚀
colorFrom: yellow
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# 🏢 Đồ án: Hệ Thống Thông Tin Quản Lý (MIS) - Odoo ERP

> **Môn học:** Đồ án thực tế Hệ thống thông tin quản lý  
> **Nền tảng triển khai:** Docker, Hugging Face Spaces & GitHub Actions  
> **Trạng thái:** Đang phát triển (Active)

## 📑 Giới thiệu dự án
Dự án này là hệ thống ERP được xây dựng và tùy biến dựa trên nền tảng mã nguồn mở **Odoo**. Mục tiêu của đồ án là ứng dụng lý thuyết Hệ thống thông tin quản lý vào thực tế doanh nghiệp, tập trung vào việc số hóa và tự động hóa các quy trình cốt lõi.

Đặc biệt, hệ thống đi sâu vào phân hệ **Quản lý Mua hàng (Purchasing)**, tích hợp các quy trình phê duyệt, quản lý nhà cung cấp và kiểm soát kho bãi.

## 🚀 Tính năng nổi bật
* **Quản lý Mua hàng (Purchase):** Lập PO, quản lý báo giá, theo dõi nhà cung cấp.
* **Quản lý Kho (Inventory):** Kiểm soát xuất/nhập/tồn kho tự động theo đơn hàng.
* **Quy trình phê duyệt:** Phân quyền và thiết lập luồng phê duyệt chứng từ nhiều cấp.
* **Báo cáo thông minh (Reporting):** Trực quan hóa dữ liệu mua hàng và tồn kho.

## ⚙️ Cấu trúc luồng làm việc (Dành cho Team Phát triển)
Dự án áp dụng mô hình CI/CD để tự động hóa việc triển khai. Các thành viên trong nhóm không cần thao tác trực tiếp trên server, chỉ cần làm việc qua GitHub:

1. **Code & Commit:** Các thành viên viết code/tùy chỉnh modules trên máy cá nhân.
2. **Push to GitHub:** Đẩy mã nguồn lên nhánh `main` của kho lưu trữ GitHub này.
3. **Auto Deploy:** Hệ thống GitHub Actions sẽ tự động kích hoạt, đồng bộ mã nguồn sang Hugging Face Spaces.
4. **Build & Run:** Hugging Face nhận Dockerfile mới và tự động khởi động lại ứng dụng Odoo.

## 🛠️ Cài đặt Môi trường Local (Dành cho Developer)
Để chạy dự án này trên máy cá nhân, bạn cần cài đặt [Docker](https://www.docker.com/) và làm theo các bước sau:

```bash
# 1. Clone repository về máy
git clone [https://github.com/TonyHoangPhuc/Mis_Purchasing_OdooProject.git](https://github.com/TonyHoangPhuc/Mis_Purchasing_OdooProject.git)

# 2. Di chuyển vào thư mục dự án
cd Mis_Purchasing_OdooProject

# 3. Khởi chạy hệ thống bằng Docker
docker-compose up -d
