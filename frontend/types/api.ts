export type UserRole = "owner" | "manager" | "staff" | "it_admin" | string;

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export type PlanTier = "starter" | "professional" | "enterprise";

export interface CheckoutRequest {
  org_name: string;
  subsidiary_name?: string | null;
  owner_email: string;
  plan_tier: PlanTier;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface CurrentUser {
  user_id: string;
  business_id: string;
  organization_id?: string | null;
  email: string;
  role: UserRole;
  full_name: string;
  avatar_url?: string | null;
  plan_tier?: string | null;
  trial_ends_at?: string | null;
}

// ─── Organization / Subsidiary / Invitations ─────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  plan_tier: string;
  subscription_status: string;
  domains: string[];
}

export interface OrganizationDomain {
  id: string;
  domain: string;
  verified: boolean;
  is_primary: boolean;
}

export interface Subsidiary {
  id: string;
  organization_id: string;
  name: string;
  email: string;
  phone: string | null;
  is_primary_subsidiary: boolean;
  is_active: boolean;
  user_count: number;
}

export interface SubsidiaryListResponse {
  total: number;
  items: Subsidiary[];
}

export type InvitationStatus = "pending" | "accepted" | "revoked" | "expired";

export interface UserInvitation {
  id: string;
  business_id: string;
  organization_id: string;
  email: string;
  role: UserRole;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
}

export interface InvitationListResponse {
  total: number;
  items: UserInvitation[];
}

export interface InvitationValidateResponse {
  organization_name: string;
  business_name: string;
  masked_email: string;
  role: UserRole;
}

export interface BusinessUser {
  id: string;
  business_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface BusinessUserListResponse {
  total: number;
  items: BusinessUser[];
}

// ─── Platform (vendor staff) console ──────────────────────────────────────────

export type PlatformRole = "support" | "billing_ops" | "admin" | "super_admin";

export interface PlatformLoginRequest {
  email: string;
  password: string;
}

export interface PlatformTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface CurrentPlatformAdmin {
  platform_admin_id: string;
  email: string;
  full_name: string;
  platform_role: PlatformRole;
  impersonation_allowed: boolean;
}

export interface PlatformStats {
  total_organizations: number;
  total_tenants: number;
  total_users: number;
  active_users: number;
  total_events: number;
  total_workflow_runs: number;
  workflow_runs_failed: number;
  organizations_by_plan_tier: Record<string, number>;
  mrr_zar: number;
  trial_conversion_rate: number | null;
}

export interface OrganizationAdmin {
  id: string;
  name: string;
  billing_email: string;
  plan_tier: string;
  subscription_status: string;
  seats_included: number | null;
  subsidiary_count: number;
  user_count: number;
}

export interface OrganizationAdminListResponse {
  total: number;
  items: OrganizationAdmin[];
}

export interface OrganizationProvisionRequest {
  org_name: string;
  billing_email: string;
  owner_email: string;
  subsidiary_name?: string;
  primary_domain?: string;
  plan_tier?: string;
}

export interface OrganizationAdminUpdate {
  name?: string;
  plan_tier?: string;
  subscription_status?: string;
  seats_included?: number;
}

export interface OrganizationEmailConfig {
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_password_set: boolean;
  smtp_from_email: string | null;
  smtp_from_name: string | null;
}

export interface OrganizationEmailConfigUpdate {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password?: string | null;
  smtp_from_email: string;
  smtp_from_name: string;
}

export interface DashboardSalesKPIs {
  revenue_total: string;
  revenue_this_month: string;
  open_orders: number;
  orders_total: number;
}

export interface DashboardLeadKPIs {
  open_leads: number;
  new_leads: number;
  qualified_leads: number;
  won_leads: number;
  lost_leads: number;
}

export interface DashboardTaskKPIs {
  overdue: number;
  due_today: number;
  pending: number;
}

export interface DashboardInventoryKPIs {
  low_stock_products: number;
  out_of_stock_products: number;
  total_active_products: number;
  total_suppliers: number;
}

export interface DashboardWorkflowKPIs {
  total_definitions: number;
  active_runs: number;
  failed_runs_today: number;
}

export interface DashboardMetricsResponse {
  sales: DashboardSalesKPIs;
  leads: DashboardLeadKPIs;
  tasks: DashboardTaskKPIs;
  inventory: DashboardInventoryKPIs;
  workflows: DashboardWorkflowKPIs;
  refreshedAt: string;
}

export interface OnboardingStepResponse {
  key: string;
  done: boolean;
}

export interface OnboardingChecklistResponse {
  steps: OnboardingStepResponse[];
}

export interface WorkflowAction {
  id: string;
  workflow_id: string | null;
  action_type: string;
  parameters: Record<string, unknown>;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface Workflow {
  id: string;
  business_id: string;
  name: string;
  description: string | null;
  trigger_event_type: string;
  enabled: boolean;
  order: number;
  actions: WorkflowAction[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowListResponse {
  total: number;
  workflows: Workflow[];
}

export interface WorkflowActionInput {
  action_type: string;
  parameters: Record<string, unknown>;
  order: number;
}

export interface WorkflowDefinitionInput {
  trigger_event_type: string;
  enabled: boolean;
  order: number;
  actions: WorkflowActionInput[];
}

export type WorkflowRunStatus = "queued" | "running" | "completed" | "failed";

export interface WorkflowRun {
  id: string;
  workflow_id: string | null;
  workflow_definition_id: string | null;
  business_id: string;
  event_id: string | null;
  triggered_by_event_id: string | null;
  actor_id: string | null;
  status: WorkflowRunStatus;
  definition_snapshot: Record<string, unknown>;
  error_message: string | null;
  results: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface WorkflowRunListResponse {
  total: number;
  runs: WorkflowRun[];
}

export type LeadStatusBackend = "new" | "contacted" | "qualified" | "won" | "lost";

export interface Lead {
  id: string;
  business_id: string;
  customer_id: string | null;
  assigned_to: string | null;
  status: LeadStatusBackend;
  source: string | null;
  value: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  skip: number;
  limit: number;
}

export interface LeadGenSearchResponse {
  created_count: number;
  qualified_count: number;
  skipped_duplicates: number;
  skipped_closed: number;
  leads: Lead[];
}

export interface Customer {
  id: string;
  business_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  skip: number;
  limit: number;
}

export type TaskStatusBackend = "pending" | "in_progress" | "completed" | "overdue";
export type TaskPriorityBackend = "low" | "medium" | "high" | "urgent";

export interface Task {
  id: string;
  business_id: string;
  lead_id: string | null;
  assigned_to: string | null;
  assignee_ids: string[];
  title: string;
  description: string | null;
  status: TaskStatusBackend;
  priority: TaskPriorityBackend;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  skip: number;
  limit: number;
}

// ─── ERP: Products ────────────────────────────────────────────────────────────

export type ProductType = "physical" | "digital" | "service";

export interface Product {
  id: string;
  business_id: string;
  sku: string;
  name: string;
  description: string | null;
  product_type: ProductType;
  category: string | null;
  unit_price: string;
  cost_price: string | null;
  tax_rate: string;
  is_active: boolean;
  track_inventory: boolean;
  barcode: string | null;
  weight: string | null;
  weight_unit: string;
  meta_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  skip: number;
  limit: number;
}

// ─── ERP: Suppliers ───────────────────────────────────────────────────────────

export interface Supplier {
  id: string;
  business_id: string;
  name: string;
  code: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  payment_terms: string | null;
  tax_id: string | null;
  is_active: boolean;
  rating: number | null;
  notes: string | null;
  meta_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SupplierListResponse {
  items: Supplier[];
  total: number;
  skip: number;
  limit: number;
}

// ─── ERP: Inventory ───────────────────────────────────────────────────────────

export interface InventoryLocation {
  id: string;
  business_id: string;
  name: string;
  code: string | null;
  location_type: string;
  is_active: boolean;
  meta_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StockLevel {
  id: string;
  product_id: string;
  location_id: string;
  quantity: number;
  reserved: number;
  available: number;
  reorder_point: number;
  reorder_quantity: number;
  created_at: string;
  updated_at: string;
}

// ─── ERP: Sales Orders ────────────────────────────────────────────────────────

export type SalesOrderStatus =
  | "draft"
  | "confirmed"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled";

export interface OrderLineItem {
  id: string;
  order_id: string;
  product_id: string | null;
  quantity: number;
  unit_price: string;
  subtotal: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SalesOrder {
  id: string;
  business_id: string;
  order_number: string;
  customer_id: string | null;
  status: SalesOrderStatus;
  order_date: string | null;
  total_amount: string;
  tracking_number: string | null;
  carrier: string | null;
  notes: string | null;
  meta_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  line_items: OrderLineItem[];
}

export interface SalesOrderListResponse {
  items: SalesOrder[];
  total: number;
  skip: number;
  limit: number;
}

// ─── ERP: Purchase Orders ─────────────────────────────────────────────────────

export type PurchaseOrderStatus =
  | "draft"
  | "sent"
  | "confirmed"
  | "partially_received"
  | "received"
  | "cancelled";

export interface POLineItem {
  id: string;
  po_id: string;
  product_id: string | null;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost: string;
  subtotal: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrder {
  id: string;
  business_id: string;
  po_number: string;
  supplier_id: string | null;
  status: PurchaseOrderStatus;
  order_date: string | null;
  expected_date: string | null;
  received_date: string | null;
  total_cost: string;
  notes: string | null;
  receiving_location_id: string | null;
  meta_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  line_items: POLineItem[];
}

export interface PurchaseOrderListResponse {
  items: PurchaseOrder[];
  total: number;
  skip: number;
  limit: number;
}

// ─── ERP: Purchase Requisitions ────────────────────────────────────────────────

export type PurchaseRequisitionStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled"
  | "converted";

export interface PRLineItem {
  id: string;
  requisition_id: string;
  product_id: string | null;
  description: string;
  quantity: number;
  estimated_unit_cost: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseRequisition {
  id: string;
  business_id: string;
  requested_by: string | null;
  supplier_id: string | null;
  title: string;
  justification: string | null;
  estimated_total: string;
  status: PurchaseRequisitionStatus;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  converted_purchase_order_id: string | null;
  created_at: string;
  updated_at: string;
  line_items: PRLineItem[];
}

export interface PurchaseRequisitionListResponse {
  items: PurchaseRequisition[];
  total: number;
  skip: number;
  limit: number;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatAction {
  id: string;
  action_type: "create_task" | "update_lead_status" | "add_note";
  arguments: Record<string, unknown>;
  description: string;
  status: "pending" | "confirmed" | "cancelled" | "executed" | "failed";
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  mentions_data: ResolvedMention[];
  actions_data: ChatAction[];
  created_at: string;
}

export interface ChatConversation {
  id: string;
  business_id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatConversationDetail extends ChatConversation {
  messages: ChatMessage[];
}

export interface ResolvedMention {
  type: string;
  value: string;
  found: boolean;
  entity_id: string | null;
  display_name: string;
}

export interface SendMessageResponse {
  conversation_id: string;
  reply: string;
  resolved_mentions: ResolvedMention[];
  user_message_id: string;
  assistant_message_id: string;
  actions: ChatAction[];
}

export interface MentionSearchResult {
  id: string;
  label: string;
  sub: string;
}

// ─── Events (Audit Log) ───────────────────────────────────────────────────────

export interface BusinessEvent {
  id: string;
  business_id: string;
  actor_id: string | null;
  event_type: string;
  entity_type: string;
  entity_id: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EventListResponse {
  items: BusinessEvent[];
  total: number;
  skip: number;
  limit: number;
}

// ─── Documents (file attachments) ─────────────────────────────────────────────

export interface BusinessDocument {
  id: string;
  business_id: string;
  entity_type: string;
  entity_id: string;
  uploaded_by: string | null;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  restricted: boolean;
  has_access: boolean;
  version: number;
  checked_out_by: string | null;
  checked_out_at: string | null;
  created_at: string;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  uploaded_by: string | null;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
}

export interface DocumentVersionListResponse {
  items: DocumentVersion[];
}

export interface BusinessFolder {
  id: string;
  business_id: string;
  parent_folder_id: string | null;
  name: string;
  created_by: string | null;
  created_at: string;
}

export interface FolderListResponse {
  items: BusinessFolder[];
}

export interface DocumentAccessRequest {
  id: string;
  document_id: string;
  user_id: string;
  status: "pending" | "approved" | "denied";
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface DocumentAccessRequestListResponse {
  items: DocumentAccessRequest[];
}

export interface DocumentListResponse {
  items: BusinessDocument[];
  total: number;
}

export interface DocumentDownloadResponse {
  url: string;
  expires_in: number;
}

export interface DocumentShareLink {
  id: string;
  document_id: string;
  url: string;
  created_by: string | null;
  expires_at: string;
  created_at: string;
}

export interface DocumentShareLinkListResponse {
  items: DocumentShareLink[];
}

// ─── Org Chart ────────────────────────────────────────────────────────────

export interface OrgChartNode {
  id: string;
  full_name: string;
  position: string | null;
  department_name: string | null;
  manager_id: string | null;
  is_active: boolean;
  email: string | null;
}

// ─── Meetings / Calls ─────────────────────────────────────────────────────

export type MeetingCallType = "voice" | "video";
export type MeetingStatus = "scheduled" | "in_progress" | "completed" | "cancelled";
export type MeetingResponseStatus = "pending" | "accepted" | "declined";

export interface MeetingParticipant {
  user_id: string;
  full_name: string;
  email: string | null;
  response_status: MeetingResponseStatus;
  joined_at: string | null;
}

export interface MeetingExternalParticipant {
  email: string;
  response_status: MeetingResponseStatus;
  responded_at: string | null;
}

export interface Meeting {
  id: string;
  business_id: string;
  organizer_id: string | null;
  organizer_name: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  call_type: MeetingCallType;
  status: MeetingStatus;
  created_at: string;
  participants: MeetingParticipant[];
  external_participants: MeetingExternalParticipant[];
}

export interface MeetingRsvpDetail {
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  call_type: MeetingCallType;
  organizer_name: string;
  response_status: MeetingResponseStatus;
}

export interface MeetingListResponse {
  items: Meeting[];
  total: number;
  skip: number;
  limit: number;
}

export interface AgoraJoinResponse {
  agora_app_id: string;
  channel_name: string;
  token: string;
  uid: number;
  expires_at: string;
}

// ─── Direct Messages (colleague chat) ────────────────────────────────────

export interface OtherUser {
  id: string;
  full_name: string;
  email: string;
}

export interface LastMessagePreview {
  content: string;
  created_at: string;
  sender_id: string | null;
}

export interface Conversation {
  id: string;
  other_user: OtherUser;
  last_message: LastMessagePreview | null;
  unread_count: number;
}

export interface ConversationListResponse {
  items: Conversation[];
}

export type MessageType = "text" | "document" | "image" | "video" | "audio" | "contact" | "poll" | "event" | "sticker";

export interface MessageAttachment {
  id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  kind: "document" | "image" | "video" | "audio";
  download_url: string | null;
}

export interface SharedCustomer {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
}

export interface SharedMeeting {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  call_type: string;
  status: string;
}

export interface PollOption {
  id: string;
  text: string;
  vote_count: number;
}

export interface Poll {
  id: string;
  question: string;
  allow_multiple: boolean;
  options: PollOption[];
  my_vote_option_ids: string[];
  total_votes: number;
}

export interface DirectMessage {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  sender_name: string;
  content: string | null;
  message_type: MessageType;
  created_at: string;
  attachment: MessageAttachment | null;
  shared_customer: SharedCustomer | null;
  shared_meeting: SharedMeeting | null;
  poll: Poll | null;
  sticker_key: string | null;
}

export interface MessageListResponse {
  items: DirectMessage[];
}

// ─── Email (personal inbox) ──────────────────────────────────────────────

export interface UserEmailAccount {
  imap_host: string | null;
  imap_port: number | null;
  imap_username: string | null;
  imap_password_set: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_password_set: boolean;
  smtp_from_email: string | null;
  smtp_from_name: string | null;
}

export interface EmailMessageSummary {
  uid: string;
  from_address: string;
  subject: string;
  date: string | null;
  is_read: boolean;
}

export interface EmailMessageDetail {
  uid: string;
  from_address: string;
  to_address: string;
  subject: string;
  date: string | null;
  body_html: string | null;
  body_text: string | null;
}

export interface EmailListResponse {
  items: EmailMessageSummary[];
}
