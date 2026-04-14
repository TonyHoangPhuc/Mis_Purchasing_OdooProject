--
-- PostgreSQL database dump
--

-- Dumped from database version 12.4
-- Dumped by pg_dump version 12.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: mer_purchase_request; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.mer_purchase_request (
    id integer NOT NULL,
    user_id integer,
    manager_id integer,
    partner_id integer,
    warehouse_id integer NOT NULL,
    purchase_id integer,
    create_uid integer,
    write_uid integer,
    name character varying NOT NULL,
    state character varying,
    date_request date,
    notes text,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    store_id integer
);


ALTER TABLE public.mer_purchase_request OWNER TO admin;

--
-- Name: TABLE mer_purchase_request; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.mer_purchase_request IS 'Yêu cầu mua hàng Merchandise';


--
-- Name: COLUMN mer_purchase_request.user_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.user_id IS 'Người tạo';


--
-- Name: COLUMN mer_purchase_request.manager_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.manager_id IS 'Người phê duyệt';


--
-- Name: COLUMN mer_purchase_request.partner_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.partner_id IS 'Kho tổng / Nhà cung cấp';


--
-- Name: COLUMN mer_purchase_request.warehouse_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.warehouse_id IS 'Cửa hàng';


--
-- Name: COLUMN mer_purchase_request.purchase_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.purchase_id IS 'Đơn mua hàng (PO)';


--
-- Name: COLUMN mer_purchase_request.create_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.create_uid IS 'Created by';


--
-- Name: COLUMN mer_purchase_request.write_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.write_uid IS 'Last Updated by';


--
-- Name: COLUMN mer_purchase_request.name; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.name IS 'Mã yêu cầu';


--
-- Name: COLUMN mer_purchase_request.state; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.state IS 'Trạng thái';


--
-- Name: COLUMN mer_purchase_request.date_request; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.date_request IS 'Ngày yêu cầu';


--
-- Name: COLUMN mer_purchase_request.notes; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.notes IS 'Ghi chú';


--
-- Name: COLUMN mer_purchase_request.create_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.create_date IS 'Created on';


--
-- Name: COLUMN mer_purchase_request.write_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.write_date IS 'Last Updated on';


--
-- Name: COLUMN mer_purchase_request.store_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request.store_id IS 'Cửa hàng yêu cầu';


--
-- Name: mer_purchase_request_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.mer_purchase_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mer_purchase_request_id_seq OWNER TO admin;

--
-- Name: mer_purchase_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.mer_purchase_request_id_seq OWNED BY public.mer_purchase_request.id;


--
-- Name: mer_purchase_request_line; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.mer_purchase_request_line (
    id integer NOT NULL,
    request_id integer,
    product_id integer NOT NULL,
    create_uid integer,
    write_uid integer,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    product_qty double precision,
    source_warehouse_id integer,
    supplier_id integer,
    purchase_order_id integer,
    internal_picking_id integer,
    fulfillment_method character varying,
    internal_flow_state character varying
);


ALTER TABLE public.mer_purchase_request_line OWNER TO admin;

--
-- Name: TABLE mer_purchase_request_line; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.mer_purchase_request_line IS 'Chi tiết sản phẩm yêu cầu mua hàng';


--
-- Name: COLUMN mer_purchase_request_line.request_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.request_id IS 'Yêu cầu';


--
-- Name: COLUMN mer_purchase_request_line.product_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.product_id IS 'Sản phẩm';


--
-- Name: COLUMN mer_purchase_request_line.create_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.create_uid IS 'Created by';


--
-- Name: COLUMN mer_purchase_request_line.write_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.write_uid IS 'Last Updated by';


--
-- Name: COLUMN mer_purchase_request_line.create_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.create_date IS 'Created on';


--
-- Name: COLUMN mer_purchase_request_line.write_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.write_date IS 'Last Updated on';


--
-- Name: COLUMN mer_purchase_request_line.product_qty; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.product_qty IS 'Số lượng';


--
-- Name: COLUMN mer_purchase_request_line.source_warehouse_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.source_warehouse_id IS 'Kho nguồn';


--
-- Name: COLUMN mer_purchase_request_line.supplier_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.supplier_id IS 'Nhà cung cấp';


--
-- Name: COLUMN mer_purchase_request_line.purchase_order_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.purchase_order_id IS 'PO đã tạo';


--
-- Name: COLUMN mer_purchase_request_line.internal_picking_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.internal_picking_id IS 'Phiếu điều chuyển';


--
-- Name: COLUMN mer_purchase_request_line.fulfillment_method; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.fulfillment_method IS 'Phương án đáp ứng';


--
-- Name: COLUMN mer_purchase_request_line.internal_flow_state; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.mer_purchase_request_line.internal_flow_state IS 'Luong noi bo';


--
-- Name: mer_purchase_request_line_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.mer_purchase_request_line_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mer_purchase_request_line_id_seq OWNER TO admin;

--
-- Name: mer_purchase_request_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.mer_purchase_request_line_id_seq OWNED BY public.mer_purchase_request_line.id;


--
-- Name: purchase_order; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_order (
    id integer NOT NULL,
    partner_id integer NOT NULL,
    dest_address_id integer,
    currency_id integer NOT NULL,
    invoice_count integer,
    fiscal_position_id integer,
    payment_term_id integer,
    incoterm_id integer,
    user_id integer,
    company_id integer NOT NULL,
    reminder_date_before_receipt integer,
    create_uid integer,
    write_uid integer,
    access_token character varying,
    name character varying NOT NULL,
    priority character varying,
    origin character varying,
    partner_ref character varying,
    state character varying,
    invoice_status character varying,
    note text,
    amount_untaxed numeric,
    amount_tax numeric,
    amount_total numeric,
    amount_total_cc numeric,
    currency_rate numeric,
    locked boolean,
    acknowledged boolean,
    receipt_reminder_email boolean,
    date_order timestamp without time zone NOT NULL,
    date_approve timestamp without time zone,
    date_planned timestamp without time zone,
    date_calendar_start timestamp without time zone,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    picking_type_id integer NOT NULL,
    incoterm_location character varying,
    receipt_status character varying,
    effective_date timestamp without time zone
);


ALTER TABLE public.purchase_order OWNER TO admin;

--
-- Name: TABLE purchase_order; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.purchase_order IS 'Purchase Order';


--
-- Name: COLUMN purchase_order.partner_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.partner_id IS 'Vendor';


--
-- Name: COLUMN purchase_order.dest_address_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.dest_address_id IS 'Dropship Address';


--
-- Name: COLUMN purchase_order.currency_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.currency_id IS 'Currency';


--
-- Name: COLUMN purchase_order.invoice_count; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.invoice_count IS 'Bill Count';


--
-- Name: COLUMN purchase_order.fiscal_position_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.fiscal_position_id IS 'Fiscal Position';


--
-- Name: COLUMN purchase_order.payment_term_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.payment_term_id IS 'Payment Terms';


--
-- Name: COLUMN purchase_order.incoterm_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.incoterm_id IS 'Incoterm';


--
-- Name: COLUMN purchase_order.user_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.user_id IS 'Buyer';


--
-- Name: COLUMN purchase_order.company_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.company_id IS 'Company';


--
-- Name: COLUMN purchase_order.reminder_date_before_receipt; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.reminder_date_before_receipt IS 'Days Before Receipt';


--
-- Name: COLUMN purchase_order.create_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.create_uid IS 'Created by';


--
-- Name: COLUMN purchase_order.write_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.write_uid IS 'Last Updated by';


--
-- Name: COLUMN purchase_order.access_token; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.access_token IS 'Security Token';


--
-- Name: COLUMN purchase_order.name; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.name IS 'Order Reference';


--
-- Name: COLUMN purchase_order.priority; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.priority IS 'Priority';


--
-- Name: COLUMN purchase_order.origin; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.origin IS 'Source';


--
-- Name: COLUMN purchase_order.partner_ref; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.partner_ref IS 'Vendor Reference';


--
-- Name: COLUMN purchase_order.state; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.state IS 'Status';


--
-- Name: COLUMN purchase_order.invoice_status; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.invoice_status IS 'Billing Status';


--
-- Name: COLUMN purchase_order.note; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.note IS 'Terms and Conditions';


--
-- Name: COLUMN purchase_order.amount_untaxed; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.amount_untaxed IS 'Untaxed Amount';


--
-- Name: COLUMN purchase_order.amount_tax; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.amount_tax IS 'Taxes';


--
-- Name: COLUMN purchase_order.amount_total; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.amount_total IS 'Total';


--
-- Name: COLUMN purchase_order.amount_total_cc; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.amount_total_cc IS 'Total in currency';


--
-- Name: COLUMN purchase_order.currency_rate; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.currency_rate IS 'Currency Rate';


--
-- Name: COLUMN purchase_order.locked; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.locked IS 'Locked';


--
-- Name: COLUMN purchase_order.acknowledged; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.acknowledged IS 'Acknowledged';


--
-- Name: COLUMN purchase_order.receipt_reminder_email; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.receipt_reminder_email IS 'Receipt Reminder Email';


--
-- Name: COLUMN purchase_order.date_order; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.date_order IS 'Order Deadline';


--
-- Name: COLUMN purchase_order.date_approve; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.date_approve IS 'Confirmation Date';


--
-- Name: COLUMN purchase_order.date_planned; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.date_planned IS 'Expected Arrival';


--
-- Name: COLUMN purchase_order.date_calendar_start; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.date_calendar_start IS 'Date Calendar Start';


--
-- Name: COLUMN purchase_order.create_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.create_date IS 'Created on';


--
-- Name: COLUMN purchase_order.write_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.write_date IS 'Last Updated on';


--
-- Name: COLUMN purchase_order.picking_type_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.picking_type_id IS 'Deliver To';


--
-- Name: COLUMN purchase_order.incoterm_location; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.incoterm_location IS 'Incoterm Location';


--
-- Name: COLUMN purchase_order.receipt_status; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.receipt_status IS 'Receipt Status';


--
-- Name: COLUMN purchase_order.effective_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order.effective_date IS 'Arrival';


--
-- Name: purchase_order_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.purchase_order_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.purchase_order_id_seq OWNER TO admin;

--
-- Name: purchase_order_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.purchase_order_id_seq OWNED BY public.purchase_order.id;


--
-- Name: purchase_order_line; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_order_line (
    id integer NOT NULL,
    sequence integer,
    product_uom_id integer,
    product_id integer,
    order_id integer NOT NULL,
    company_id integer,
    partner_id integer,
    create_uid integer,
    write_uid integer,
    qty_received_method character varying,
    display_type character varying,
    analytic_distribution jsonb,
    name text NOT NULL,
    product_qty numeric NOT NULL,
    discount numeric,
    price_unit numeric NOT NULL,
    price_subtotal numeric,
    price_total numeric,
    qty_invoiced numeric,
    qty_received numeric,
    qty_received_manual numeric,
    qty_to_invoice numeric,
    is_downpayment boolean,
    date_planned timestamp without time zone,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    product_uom_qty double precision,
    price_tax double precision,
    technical_price_unit double precision,
    orderpoint_id integer,
    location_final_id integer,
    product_description_variants character varying,
    propagate_cancel boolean,
    sale_line_id integer,
    CONSTRAINT purchase_order_line_accountable_required_fields CHECK (((display_type IS NOT NULL) OR is_downpayment OR ((product_id IS NOT NULL) AND (product_uom_id IS NOT NULL) AND (date_planned IS NOT NULL)))),
    CONSTRAINT purchase_order_line_non_accountable_null_fields CHECK (((display_type IS NULL) OR ((product_id IS NULL) AND (price_unit = (0)::numeric) AND (product_uom_qty = (0)::double precision) AND (product_uom_id IS NULL) AND (date_planned IS NULL))))
);


ALTER TABLE public.purchase_order_line OWNER TO admin;

--
-- Name: TABLE purchase_order_line; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.purchase_order_line IS 'Purchase Order Line';


--
-- Name: COLUMN purchase_order_line.sequence; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.sequence IS 'Sequence';


--
-- Name: COLUMN purchase_order_line.product_uom_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.product_uom_id IS 'Unit';


--
-- Name: COLUMN purchase_order_line.product_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.product_id IS 'Product';


--
-- Name: COLUMN purchase_order_line.order_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.order_id IS 'Order Reference';


--
-- Name: COLUMN purchase_order_line.company_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.company_id IS 'Company';


--
-- Name: COLUMN purchase_order_line.partner_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.partner_id IS 'Partner';


--
-- Name: COLUMN purchase_order_line.create_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.create_uid IS 'Created by';


--
-- Name: COLUMN purchase_order_line.write_uid; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.write_uid IS 'Last Updated by';


--
-- Name: COLUMN purchase_order_line.qty_received_method; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.qty_received_method IS 'Received Qty Method';


--
-- Name: COLUMN purchase_order_line.display_type; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.display_type IS 'Display Type';


--
-- Name: COLUMN purchase_order_line.analytic_distribution; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.analytic_distribution IS 'Analytic Distribution';


--
-- Name: COLUMN purchase_order_line.name; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.name IS 'Description';


--
-- Name: COLUMN purchase_order_line.product_qty; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.product_qty IS 'Quantity';


--
-- Name: COLUMN purchase_order_line.discount; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.discount IS 'Discount (%)';


--
-- Name: COLUMN purchase_order_line.price_unit; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.price_unit IS 'Unit Price';


--
-- Name: COLUMN purchase_order_line.price_subtotal; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.price_subtotal IS 'Subtotal';


--
-- Name: COLUMN purchase_order_line.price_total; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.price_total IS 'Total';


--
-- Name: COLUMN purchase_order_line.qty_invoiced; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.qty_invoiced IS 'Billed Qty';


--
-- Name: COLUMN purchase_order_line.qty_received; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.qty_received IS 'Received Qty';


--
-- Name: COLUMN purchase_order_line.qty_received_manual; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.qty_received_manual IS 'Manual Received Qty';


--
-- Name: COLUMN purchase_order_line.qty_to_invoice; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.qty_to_invoice IS 'To Invoice Quantity';


--
-- Name: COLUMN purchase_order_line.is_downpayment; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.is_downpayment IS 'Is Downpayment';


--
-- Name: COLUMN purchase_order_line.date_planned; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.date_planned IS 'Expected Arrival';


--
-- Name: COLUMN purchase_order_line.create_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.create_date IS 'Created on';


--
-- Name: COLUMN purchase_order_line.write_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.write_date IS 'Last Updated on';


--
-- Name: COLUMN purchase_order_line.product_uom_qty; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.product_uom_qty IS 'Total Quantity';


--
-- Name: COLUMN purchase_order_line.price_tax; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.price_tax IS 'Tax';


--
-- Name: COLUMN purchase_order_line.technical_price_unit; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.technical_price_unit IS 'Technical Price Unit';


--
-- Name: COLUMN purchase_order_line.orderpoint_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.orderpoint_id IS 'Orderpoint';


--
-- Name: COLUMN purchase_order_line.location_final_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.location_final_id IS 'Location from procurement';


--
-- Name: COLUMN purchase_order_line.product_description_variants; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.product_description_variants IS 'Custom Description';


--
-- Name: COLUMN purchase_order_line.propagate_cancel; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.propagate_cancel IS 'Propagate cancellation';


--
-- Name: COLUMN purchase_order_line.sale_line_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.purchase_order_line.sale_line_id IS 'Origin Sale Item';


--
-- Name: CONSTRAINT purchase_order_line_accountable_required_fields ON purchase_order_line; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON CONSTRAINT purchase_order_line_accountable_required_fields ON public.purchase_order_line IS 'CHECK(display_type IS NOT NULL OR is_downpayment OR (product_id IS NOT NULL AND product_uom_id IS NOT NULL AND date_planned IS NOT NULL))';


--
-- Name: CONSTRAINT purchase_order_line_non_accountable_null_fields ON purchase_order_line; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON CONSTRAINT purchase_order_line_non_accountable_null_fields ON public.purchase_order_line IS 'CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom_id IS NULL AND date_planned is NULL))';


--
-- Name: purchase_order_line_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.purchase_order_line_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.purchase_order_line_id_seq OWNER TO admin;

--
-- Name: purchase_order_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.purchase_order_line_id_seq OWNED BY public.purchase_order_line.id;


--
-- Name: purchase_order_stock_picking_rel; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.purchase_order_stock_picking_rel (
    purchase_order_id integer NOT NULL,
    stock_picking_id integer NOT NULL
);


ALTER TABLE public.purchase_order_stock_picking_rel OWNER TO admin;

--
-- Name: TABLE purchase_order_stock_picking_rel; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.purchase_order_stock_picking_rel IS 'RELATION BETWEEN purchase_order AND stock_picking';


--
-- Name: stock_reference_purchase_rel; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.stock_reference_purchase_rel (
    purchase_id integer NOT NULL,
    reference_id integer NOT NULL
);


ALTER TABLE public.stock_reference_purchase_rel OWNER TO admin;

--
-- Name: TABLE stock_reference_purchase_rel; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.stock_reference_purchase_rel IS 'RELATION BETWEEN purchase_order AND stock_reference';


--
-- Name: mer_purchase_request id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request ALTER COLUMN id SET DEFAULT nextval('public.mer_purchase_request_id_seq'::regclass);


--
-- Name: mer_purchase_request_line id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line ALTER COLUMN id SET DEFAULT nextval('public.mer_purchase_request_line_id_seq'::regclass);


--
-- Name: purchase_order id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_id_seq'::regclass);


--
-- Name: purchase_order_line id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_line_id_seq'::regclass);


--
-- Data for Name: mer_purchase_request; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.mer_purchase_request (id, user_id, manager_id, partner_id, warehouse_id, purchase_id, create_uid, write_uid, name, state, date_request, notes, create_date, write_date, store_id) FROM stdin;
11	2	2	\N	9	7	2	2	PR/00011	po_created	2026-04-14	\N	2026-04-14 04:48:07.966564	2026-04-14 04:53:21.339597	8
5	2	2	1	9	2	2	2	PR/00005	po_created	2026-04-14	PR được tạo tự động từ định mức tồn kho của cửa hàng.	2026-04-14 03:04:27.288592	2026-04-14 03:06:46.569422	8
3	2	2	1	8	3	2	2	PR/00003	po_created	2026-04-14	PR được tạo tự động từ định mức tồn kho của cửa hàng.	2026-04-14 03:03:23.272507	2026-04-14 03:07:13.17308	7
10	2	2	\N	8	4	2	2	PR/00010	po_created	2026-04-14	\N	2026-04-14 04:30:02.229721	2026-04-14 04:33:38.819187	7
8	2	2	\N	8	6	2	2	PR/00008	po_created	2026-04-14	\N	2026-04-14 04:09:17.735202	2026-04-14 04:46:54.265649	7
\.


--
-- Data for Name: mer_purchase_request_line; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.mer_purchase_request_line (id, request_id, product_id, create_uid, write_uid, create_date, write_date, product_qty, source_warehouse_id, supplier_id, purchase_order_id, internal_picking_id, fulfillment_method, internal_flow_state) FROM stdin;
1	\N	1	2	2	2026-04-13 13:17:05.389419	2026-04-13 13:17:05.389419	5	\N	\N	\N	\N	\N	not_applicable
2	\N	3	2	2	2026-04-14 02:55:00.818586	2026-04-14 02:55:00.818586	500	\N	\N	\N	\N	\N	not_applicable
3	\N	2	2	2	2026-04-14 02:55:00.818586	2026-04-14 02:55:00.818586	500	\N	\N	\N	\N	\N	not_applicable
4	3	3	2	2	2026-04-14 03:03:23.272507	2026-04-14 03:03:23.272507	500	\N	\N	\N	\N	\N	not_applicable
5	3	2	2	2	2026-04-14 03:03:23.272507	2026-04-14 03:03:23.272507	500	\N	\N	\N	\N	\N	not_applicable
8	5	1	2	2	2026-04-14 03:04:27.288592	2026-04-14 03:04:27.288592	500	\N	\N	\N	\N	\N	not_applicable
6	\N	3	2	2	2026-04-14 03:04:17.586992	2026-04-14 03:04:17.586992	500	\N	\N	\N	\N	\N	not_applicable
7	\N	2	2	2	2026-04-14 03:04:17.586992	2026-04-14 03:04:17.586992	500	\N	\N	\N	\N	\N	not_applicable
9	\N	3	2	2	2026-04-14 03:28:17.923904	2026-04-14 03:28:17.923904	500	\N	\N	\N	\N	\N	not_applicable
10	\N	2	2	2	2026-04-14 03:28:17.923904	2026-04-14 03:28:17.923904	500	\N	\N	\N	\N	\N	not_applicable
11	\N	1	2	2	2026-04-14 03:32:58.418604	2026-04-14 03:32:58.418604	600	\N	\N	\N	\N	\N	not_applicable
13	\N	4	2	2	2026-04-14 04:27:25.727135	2026-04-14 04:27:43.171353	500	\N	\N	\N	\N	supplier	not_applicable
15	10	2	2	2	2026-04-14 04:30:02.229721	2026-04-14 04:33:38.819187	555	\N	16	4	\N	supplier	not_applicable
16	8	1	2	2	2026-04-14 04:36:55.594989	2026-04-14 04:46:54.265649	55	\N	16	6	\N	supplier	not_applicable
18	11	3	2	2	2026-04-14 04:48:07.966564	2026-04-14 04:53:21.339597	600	\N	16	7	\N	supplier	not_applicable
17	11	1	2	2	2026-04-14 04:48:07.966564	2026-04-14 04:53:21.339597	500	1	\N	\N	10	internal	not_applicable
19	11	2	2	2	2026-04-14 04:48:07.966564	2026-04-14 04:53:21.339597	15	1	\N	\N	10	internal	not_applicable
20	11	4	2	2	2026-04-14 04:48:07.966564	2026-04-14 04:53:21.339597	30	1	\N	\N	10	internal	not_applicable
14	10	3	2	2	2026-04-14 04:30:02.229721	2026-04-14 08:04:07.157163	55	1	\N	\N	6	internal	delivered
12	8	4	2	2	2026-04-14 04:09:17.735202	2026-04-14 08:04:17.725369	500	1	\N	\N	8	internal	delivered
\.


--
-- Data for Name: purchase_order; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.purchase_order (id, partner_id, dest_address_id, currency_id, invoice_count, fiscal_position_id, payment_term_id, incoterm_id, user_id, company_id, reminder_date_before_receipt, create_uid, write_uid, access_token, name, priority, origin, partner_ref, state, invoice_status, note, amount_untaxed, amount_tax, amount_total, amount_total_cc, currency_rate, locked, acknowledged, receipt_reminder_email, date_order, date_approve, date_planned, date_calendar_start, create_date, write_date, picking_type_id, incoterm_location, receipt_status, effective_date) FROM stdin;
1	1	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00001	0	PR/00001	\N	draft	no	\N	25000	2500	27500	27500	1.0	f	t	f	2026-04-13 13:17:20	2026-04-13 13:17:20	2026-04-13 13:17:20	2026-04-13 13:17:20	2026-04-13 13:17:20.866923	2026-04-13 13:19:12.687399	1	\N	full	2026-04-13 13:18:35
3	1	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00003	0	PR/00003	\N	cancel	no	\N	10000000	1000000	11000000	11000000	1.0	f	\N	f	2026-04-14 03:07:13	2026-04-14 03:07:13	2026-04-14 03:07:13	2026-04-14 03:07:13	2026-04-14 03:07:13.17308	2026-04-14 04:34:56.835342	1	\N	\N	\N
2	1	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00002	0	PR/00005	\N	cancel	no	\N	2500000	250000	2750000	2750000	1.0	f	t	f	2026-04-14 03:06:46	2026-04-14 03:06:46	2026-04-14 03:06:46	2026-04-14 03:06:46	2026-04-14 03:06:46.569422	2026-04-14 04:35:00.511612	1	\N	full	2026-04-14 03:17:27
5	16	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00005	0	\N	\N	draft	no	\N	0	0	0	0	1.0	f	\N	f	2026-04-14 04:35:46	\N	\N	2026-04-14 04:35:46	2026-04-14 04:36:01.702767	2026-04-14 04:36:01.702767	1	\N	\N	\N
6	16	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00006	0	PR/00008	\N	purchase	to invoice	\N	275000	27500	302500	302500	1.0	f	t	f	2026-04-14 04:46:54	2026-04-14 04:46:54	2026-04-14 04:46:54	2026-04-14 04:46:54	2026-04-14 04:46:54.265649	2026-04-14 08:04:55.290881	57	\N	full	2026-04-14 08:04:55
7	16	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00007	0	PR/00011	\N	purchase	to invoice	\N	6000000	600000	6600000	6600000	1.0	f	t	f	2026-04-14 04:53:21	2026-04-14 04:53:21	2026-04-14 04:53:21	2026-04-14 04:53:21	2026-04-14 04:53:21.339597	2026-04-14 08:05:07.528438	65	\N	full	2026-04-14 08:05:07
4	16	\N	23	0	\N	\N	\N	2	1	1	2	2	\N	P00004	0	PR/00010	\N	purchase	to invoice	\N	5550000	555000	6105000	6105000	1.0	f	t	f	2026-04-14 04:33:38	2026-04-14 04:33:38	2026-04-14 04:33:38	2026-04-14 04:33:38	2026-04-14 04:33:38.819187	2026-04-14 08:05:46.37129	57	\N	full	2026-04-14 08:05:46
\.


--
-- Data for Name: purchase_order_line; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.purchase_order_line (id, sequence, product_uom_id, product_id, order_id, company_id, partner_id, create_uid, write_uid, qty_received_method, display_type, analytic_distribution, name, product_qty, discount, price_unit, price_subtotal, price_total, qty_invoiced, qty_received, qty_received_manual, qty_to_invoice, is_downpayment, date_planned, create_date, write_date, product_uom_qty, price_tax, technical_price_unit, orderpoint_id, location_final_id, product_description_variants, propagate_cancel, sale_line_id) FROM stdin;
1	10	1	1	1	1	1	2	2	stock_moves	\N	\N	Aquafina 500ml	5.00	\N	5000.0	25000	27500	0.00	5.00	\N	0.00	\N	2026-04-13 13:17:20	2026-04-13 13:17:20.866923	2026-04-13 13:19:10.757904	5	2500	5000	\N	\N	\N	t	\N
3	10	1	3	3	1	1	2	2	stock_moves	\N	\N	Revive Chanh Muối Lốc 6	500.00	\N	10000.0	5000000	5500000	0.00	0.00	\N	0.00	\N	2026-04-14 03:07:13	2026-04-14 03:07:13.17308	2026-04-14 03:07:13.17308	500	500000	10000	\N	\N	\N	t	\N
4	10	1	2	3	1	1	2	2	stock_moves	\N	\N	Revive Lốc 6	500.00	\N	10000.0	5000000	5500000	0.00	0.00	\N	0.00	\N	2026-04-14 03:07:13	2026-04-14 03:07:13.17308	2026-04-14 03:07:13.17308	500	500000	10000	\N	\N	\N	t	\N
2	10	1	1	2	1	1	2	2	stock_moves	\N	\N	Aquafina 500ml	500.00	\N	5000.0	2500000	2750000	0.00	500.00	\N	0.00	\N	2026-04-14 03:06:46	2026-04-14 03:06:46.569422	2026-04-14 04:35:00.511612	500	250000	5000	\N	\N	\N	t	\N
6	10	1	1	6	1	16	2	2	stock_moves	\N	\N	Aquafina 500ml	55.00	\N	5000.0	275000	302500	0.00	55.00	\N	55.00	\N	2026-04-14 04:46:54	2026-04-14 04:46:54.265649	2026-04-14 08:04:55.290881	55	27500	5000	\N	\N	\N	t	\N
7	10	1	3	7	1	16	2	2	stock_moves	\N	\N	Revive Chanh Muối Lốc 6	600.00	\N	10000.0	6000000	6600000	0.00	600.00	\N	600.00	\N	2026-04-14 04:53:21	2026-04-14 04:53:21.339597	2026-04-14 08:05:07.528438	600	600000	10000	\N	\N	\N	t	\N
5	10	1	2	4	1	16	2	2	stock_moves	\N	\N	Revive Lốc 6	555.00	\N	10000.0	5550000	6105000	0.00	555.00	\N	555.00	\N	2026-04-14 04:33:38	2026-04-14 04:33:38.819187	2026-04-14 08:05:46.37129	555	555000	10000	\N	\N	\N	t	\N
\.


--
-- Data for Name: purchase_order_stock_picking_rel; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.purchase_order_stock_picking_rel (purchase_order_id, stock_picking_id) FROM stdin;
1	1
2	2
3	3
4	5
6	7
7	9
\.


--
-- Data for Name: stock_reference_purchase_rel; Type: TABLE DATA; Schema: public; Owner: admin
--

COPY public.stock_reference_purchase_rel (purchase_id, reference_id) FROM stdin;
4	4
6	5
7	6
\.


--
-- Name: mer_purchase_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.mer_purchase_request_id_seq', 11, true);


--
-- Name: mer_purchase_request_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.mer_purchase_request_line_id_seq', 20, true);


--
-- Name: purchase_order_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.purchase_order_id_seq', 7, true);


--
-- Name: purchase_order_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: admin
--

SELECT pg_catalog.setval('public.purchase_order_line_id_seq', 7, true);


--
-- Name: mer_purchase_request_line mer_purchase_request_line_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_pkey PRIMARY KEY (id);


--
-- Name: mer_purchase_request mer_purchase_request_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_line purchase_order_line_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_pkey PRIMARY KEY (id);


--
-- Name: purchase_order purchase_order_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_stock_picking_rel purchase_order_stock_picking_rel_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_stock_picking_rel
    ADD CONSTRAINT purchase_order_stock_picking_rel_pkey PRIMARY KEY (purchase_order_id, stock_picking_id);


--
-- Name: stock_reference_purchase_rel stock_reference_purchase_rel_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_reference_purchase_rel
    ADD CONSTRAINT stock_reference_purchase_rel_pkey PRIMARY KEY (purchase_id, reference_id);


--
-- Name: mer_purchase_request__name_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX mer_purchase_request__name_index ON public.mer_purchase_request USING btree (name);


--
-- Name: purchase_order__company_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__company_id_index ON public.purchase_order USING btree (company_id);


--
-- Name: purchase_order__date_approve_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__date_approve_index ON public.purchase_order USING btree (date_approve);


--
-- Name: purchase_order__date_order_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__date_order_index ON public.purchase_order USING btree (date_order);


--
-- Name: purchase_order__date_planned_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__date_planned_index ON public.purchase_order USING btree (date_planned);


--
-- Name: purchase_order__name_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__name_index ON public.purchase_order USING gin (name public.gin_trgm_ops);


--
-- Name: purchase_order__partner_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__partner_id_index ON public.purchase_order USING btree (partner_id);


--
-- Name: purchase_order__priority_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__priority_index ON public.purchase_order USING btree (priority);


--
-- Name: purchase_order__state_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__state_index ON public.purchase_order USING btree (state);


--
-- Name: purchase_order__user_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order__user_id_index ON public.purchase_order USING btree (user_id);


--
-- Name: purchase_order_line__date_planned_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line__date_planned_index ON public.purchase_order_line USING btree (date_planned);


--
-- Name: purchase_order_line__order_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line__order_id_index ON public.purchase_order_line USING btree (order_id);


--
-- Name: purchase_order_line__orderpoint_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line__orderpoint_id_index ON public.purchase_order_line USING btree (orderpoint_id) WHERE (orderpoint_id IS NOT NULL);


--
-- Name: purchase_order_line__partner_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line__partner_id_index ON public.purchase_order_line USING btree (partner_id) WHERE (partner_id IS NOT NULL);


--
-- Name: purchase_order_line__product_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line__product_id_index ON public.purchase_order_line USING btree (product_id) WHERE (product_id IS NOT NULL);


--
-- Name: purchase_order_line__sale_line_id_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line__sale_line_id_index ON public.purchase_order_line USING btree (sale_line_id) WHERE (sale_line_id IS NOT NULL);


--
-- Name: purchase_order_line_analytic_distribution_accounts_gin_index; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_line_analytic_distribution_accounts_gin_index ON public.purchase_order_line USING gin (regexp_split_to_array((jsonb_path_query_array(analytic_distribution, '$.keyvalue()."key"'::jsonpath))::text, '\D+'::text));


--
-- Name: purchase_order_stock_picking__stock_picking_id_purchase_ord_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX purchase_order_stock_picking__stock_picking_id_purchase_ord_idx ON public.purchase_order_stock_picking_rel USING btree (stock_picking_id, purchase_order_id);


--
-- Name: stock_reference_purchase_rel_reference_id_purchase_id_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX stock_reference_purchase_rel_reference_id_purchase_id_idx ON public.stock_reference_purchase_rel USING btree (reference_id, purchase_id);


--
-- Name: mer_purchase_request mer_purchase_request_create_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_create_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_internal_picking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_internal_picking_id_fkey FOREIGN KEY (internal_picking_id) REFERENCES public.stock_picking(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product_product(id) ON DELETE RESTRICT;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES public.purchase_order(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.mer_purchase_request(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_source_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_source_warehouse_id_fkey FOREIGN KEY (source_warehouse_id) REFERENCES public.stock_warehouse(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.res_partner(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request_line mer_purchase_request_line_write_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request_line
    ADD CONSTRAINT mer_purchase_request_line_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request mer_purchase_request_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request mer_purchase_request_partner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.res_partner(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request mer_purchase_request_purchase_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_purchase_id_fkey FOREIGN KEY (purchase_id) REFERENCES public.purchase_order(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request mer_purchase_request_store_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_store_id_fkey FOREIGN KEY (store_id) REFERENCES public.store_store(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request mer_purchase_request_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: mer_purchase_request mer_purchase_request_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.stock_warehouse(id) ON DELETE RESTRICT;


--
-- Name: mer_purchase_request mer_purchase_request_write_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.mer_purchase_request
    ADD CONSTRAINT mer_purchase_request_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.res_company(id) ON DELETE RESTRICT;


--
-- Name: purchase_order purchase_order_create_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_currency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES public.res_currency(id) ON DELETE RESTRICT;


--
-- Name: purchase_order purchase_order_dest_address_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_dest_address_id_fkey FOREIGN KEY (dest_address_id) REFERENCES public.res_partner(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_fiscal_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_fiscal_position_id_fkey FOREIGN KEY (fiscal_position_id) REFERENCES public.account_fiscal_position(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_incoterm_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_incoterm_id_fkey FOREIGN KEY (incoterm_id) REFERENCES public.account_incoterms(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.res_company(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_create_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_location_final_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_location_final_id_fkey FOREIGN KEY (location_final_id) REFERENCES public.stock_location(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.purchase_order(id) ON DELETE CASCADE;


--
-- Name: purchase_order_line purchase_order_line_orderpoint_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_orderpoint_id_fkey FOREIGN KEY (orderpoint_id) REFERENCES public.stock_warehouse_orderpoint(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_partner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.res_partner(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product_product(id) ON DELETE RESTRICT;


--
-- Name: purchase_order_line purchase_order_line_product_uom_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_product_uom_id_fkey FOREIGN KEY (product_uom_id) REFERENCES public.uom_uom(id) ON DELETE RESTRICT;


--
-- Name: purchase_order_line purchase_order_line_sale_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_sale_line_id_fkey FOREIGN KEY (sale_line_id) REFERENCES public.sale_order_line(id) ON DELETE SET NULL;


--
-- Name: purchase_order_line purchase_order_line_write_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_line
    ADD CONSTRAINT purchase_order_line_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_partner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.res_partner(id) ON DELETE RESTRICT;


--
-- Name: purchase_order purchase_order_payment_term_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_payment_term_id_fkey FOREIGN KEY (payment_term_id) REFERENCES public.account_payment_term(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_picking_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_picking_type_id_fkey FOREIGN KEY (picking_type_id) REFERENCES public.stock_picking_type(id) ON DELETE RESTRICT;


--
-- Name: purchase_order_stock_picking_rel purchase_order_stock_picking_rel_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_stock_picking_rel
    ADD CONSTRAINT purchase_order_stock_picking_rel_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES public.purchase_order(id) ON DELETE CASCADE;


--
-- Name: purchase_order_stock_picking_rel purchase_order_stock_picking_rel_stock_picking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order_stock_picking_rel
    ADD CONSTRAINT purchase_order_stock_picking_rel_stock_picking_id_fkey FOREIGN KEY (stock_picking_id) REFERENCES public.stock_picking(id) ON DELETE CASCADE;


--
-- Name: purchase_order purchase_order_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: purchase_order purchase_order_write_uid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.purchase_order
    ADD CONSTRAINT purchase_order_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES public.res_users(id) ON DELETE SET NULL;


--
-- Name: stock_reference_purchase_rel stock_reference_purchase_rel_purchase_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_reference_purchase_rel
    ADD CONSTRAINT stock_reference_purchase_rel_purchase_id_fkey FOREIGN KEY (purchase_id) REFERENCES public.purchase_order(id) ON DELETE CASCADE;


--
-- Name: stock_reference_purchase_rel stock_reference_purchase_rel_reference_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.stock_reference_purchase_rel
    ADD CONSTRAINT stock_reference_purchase_rel_reference_id_fkey FOREIGN KEY (reference_id) REFERENCES public.stock_reference(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

