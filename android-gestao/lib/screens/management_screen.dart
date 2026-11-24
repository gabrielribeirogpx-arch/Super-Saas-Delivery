import 'package:flutter/material.dart';

import '../services/management_api.dart';
import 'dashboard_view.dart';
import 'attendance_views.dart';
import 'delivery_views.dart';
import 'more_menu.dart';
import 'marketing_view.dart';
import 'operations_views.dart';
import 'catalog_editor.dart';
import 'appearance_editor.dart';
import 'storefront_preview.dart';
import 'management_views.dart';

class ManagementScreen extends StatefulWidget {
  const ManagementScreen({super.key, required this.api});

  final ManagementApi api;

  @override
  State<ManagementScreen> createState() => _ManagementScreenState();
}

class _ManagementScreenState extends State<ManagementScreen> {
  final _form = GlobalKey<FormState>();
  final _store = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  int? _tenant;
  int _section = 1;
  Map<String, dynamic>? _catalogPreview;
  Map<String, dynamic>? _wazzaConnection;
  List<Map<String, dynamic>>? _wazzaRequests;
  List<int?> _wazzaCursors = [null];
  int? _wazzaNext;
  List<Map<String, dynamic>>? _whatsappLogs;
  bool _canViewMarketing = false;
  final _marketing = <MarketingSection, List<Map<String, dynamic>>>{};
  List<Map<String, dynamic>>? _adminUsers;
  List<Map<String, dynamic>>? _auditEvents;
  DateTimeRange? _auditPeriod;
  List<Map<String, dynamic>>? _deliveries;
  List<Map<String, dynamic>>? _deliveryUsers;
  bool _canViewManagement = false;
  bool _canViewFinance = false;
  bool _canViewReports = false;
  DateTimeRange _financePeriod = DashboardPeriod.last7.range(null);
  DateTimeRange _reportsPeriod = DashboardPeriod.last30.range(null);
  ({Map<String, dynamic> summary, List<Map<String, dynamic>> movements})? _finance;
  ({Map<String, dynamic> summary, List<Map<String, dynamic>> items,
    List<Map<String, dynamic>> lowStock})? _reports;
  DateTimeRange _inventoryPeriod = DashboardPeriod.last7.range(null);
  List<Map<String, dynamic>>? _inventoryItems;
  List<Map<String, dynamic>>? _inventoryMovements;
  List<Map<String, dynamic>>? _customers;
  int _customerPage = 1;
  int _customerTotal = 0;
  String _customerSearch = '';
  String _kitchenArea = KitchenView.areas.first;
  List<Map<String, dynamic>> _kitchenOrders = [];
  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _menuItems = [];
  Map<String, dynamic> _dashboard = {};
  DashboardPeriod _period = DashboardPeriod.last7;
  DateTimeRange? _customRange;
  bool _busy = false;
  final _customer = TextEditingController();
  final _numberFilter = TextEditingController();
  String _statusFilter = '';
  ({String customer, String number, String status}) _appliedFilters =
      (customer: '', number: '', status: '');
  int _page = 1;
  int _totalOrders = 0;
  Map<String, dynamic> _summary = {};
  String? _error;
  List<Map<String, dynamic>> _orders = [];

  @override
  void dispose() {
    _store.dispose();
    _email.dispose();
    _password.dispose();
    _customer.dispose();
    _numberFilter.dispose();
    widget.api.close();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() operation) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await operation();
    } on ManagementApiError catch (error) {
      if (mounted) {
        final wasSignedIn = _tenant != null;
        if (error.status == 401) {
          _tenant = null;
          _clearManagementData();
          _orders = [];
          _dashboard = {};
          _kitchenOrders = [];
          _categories = [];
          _menuItems = [];
        }
        _error = switch (error.status) {
          400 => 'Confira o identificador da loja.',
          401 when wasSignedIn => 'Sua sessão expirou. Entre novamente.',
          401 => 'Não foi possível entrar. Confira a loja, o e-mail e a senha.',
          409 => 'O status do pedido mudou. Atualize a lista e tente novamente.',
          403 => 'Seu usuário não tem acesso a esta operação.',
          412 => 'Confirme seu e-mail pelo painel web antes de entrar no app.',
          429 => 'Muitas tentativas. Aguarde alguns minutos.',
          _ => 'O Fomizero não conseguiu concluir a operação.',
        };
      }
    } catch (_) {
      if (mounted) _error = 'Não foi possível concluir a operação. Tente novamente.';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _login() async {
    if (!_form.currentState!.validate()) return;

    await _run(() async {
      final password = _password.text;
      _password.clear();
      final session = await widget.api.login(_store.text.trim(), _email.text.trim(), password);
      if (!mounted) return;
      setState(() {
        _tenant = session.tenantId;
        _canViewManagement = const {'admin', 'owner'}.contains(session.role);
        _canViewMarketing = _canViewManagement || session.role == 'operator';
        _canViewFinance = _canViewManagement || session.role == 'cashier';
        _canViewReports = _canViewFinance || session.role == 'operator';
        _financePeriod = DashboardPeriod.last7.range(null);
        _reportsPeriod = DashboardPeriod.last30.range(null);
        _clearManagementData();
        _auditPeriod = null;
        _inventoryPeriod = DashboardPeriod.last7.range(null);
        _customerPage = 1;
        _customerTotal = 0;
        _customerSearch = '';
        _period = DashboardPeriod.last7;
        _customRange = null;
        _section = const {'admin', 'owner', 'operator', 'cashier'}.contains(session.role) ? 0 : 1;
        _kitchenArea = KitchenView.areas.first;
        _kitchenOrders = [];
        _categories = [];
        _menuItems = [];
        _dashboard = {};
        _page = 1;
        _totalOrders = 0;
        _summary = {};
        _statusFilter = '';
        _customer.clear();
        _numberFilter.clear();
      });
      if (_section == 0) {
        await _loadDashboard();
      } else {
        await _loadOrders(session.tenantId, 1, summary: true);
      }
    });
  }

  Future<void> _loadDashboard() async {
    final range = _period.range(_customRange);
    final dashboard = await widget.api.dashboard(range.start, range.end);
    if (mounted) setState(() => _dashboard = dashboard);
  }

  Future<void> _changePeriod(DashboardPeriod period, DateTimeRange? range) async {
    if (_busy) return;
    setState(() {
      _period = period;
      _customRange = range;
      _dashboard = {};
    });
    await _run(_loadDashboard);
  }

  Future<void> _selectSection(int index) async {
    if (_busy || index == _section) return;
    setState(() => _section = index);
    await _refreshSection();
  }

  Future<void> _showMore() async {
    if (_busy) return;
    final section = await MoreMenu.show(context, [
      if (_canViewMarketing) (15, Icons.chat_outlined, 'Wazza'),
      if (_canViewManagement) (16, Icons.chat_bubble_outline, 'WhatsApp'),
      (8, Icons.local_shipping_outlined, 'Entregas'),
      if (_canViewManagement) (9, Icons.pedal_bike_outlined, 'Entregadores'),
      if (_canViewFinance) (6, Icons.account_balance_wallet_outlined, 'Financeiro'),
      if (_canViewManagement) (4, Icons.inventory_2_outlined, 'Estoque'),
      if (_canViewManagement) (17, Icons.visibility_outlined, 'Prévia do Cardápio'),
      if (_canViewReports) (7, Icons.bar_chart_outlined, 'Relatórios'),
      if (_canViewMarketing)
        for (final section in MarketingSection.values)
          (12 + section.index, section.icon, section.label),
      if (_canViewManagement) ...[
        (5, Icons.people_outline, 'Clientes'),
        (10, Icons.manage_accounts_outlined, 'Usuários'),
        (11, Icons.policy_outlined, 'Auditoria'),
      ],
    ]);
    if (mounted && section != null) await _selectSection(section);
  }

  void _clearManagementData() {
    _inventoryItems = null;
    _inventoryMovements = null;
    _customers = null;
    _finance = null;
    _reports = null;
    _deliveries = null;
    _deliveryUsers = null;
    _adminUsers = null;
    _auditEvents = null;
    _marketing.clear();
    _wazzaConnection = null;
    _wazzaRequests = null;
    _wazzaCursors = [null];
    _wazzaNext = null;
    _whatsappLogs = null;
    _catalogPreview = null;
  }

  Future<void> _loadWazza() async {
    final connection = await widget.api.wazzaConnection();
    if (!mounted) return;
    setState(() => _wazzaConnection = connection);
    await _loadWazzaPage(_wazzaCursors);
  }

  Future<void> _loadWazzaPage(List<int?> cursors) async {
    final page = await widget.api.wazzaRequests(cursors.last);
    if (!mounted) return;
    setState(() {
      _wazzaCursors = cursors;
      _wazzaRequests = page.items;
      _wazzaNext = page.next;
    });
  }

  Future<void> _decideWazza(int id, WazzaDecision action, String reason) async {
    await _run(() async {
      await widget.api.decideWazzaRequest(id, action.name, reason);
      await _loadWazzaPage(_wazzaCursors);
    });
  }

  Future<void> _loadWhatsApp() async {
    final tenant = _tenant;
    if (tenant == null) return;
    final logs = await widget.api.whatsappLogs(tenant);
    if (mounted) setState(() => _whatsappLogs = logs);
  }

  Future<void> _loadMarketing(MarketingSection section) async {
    final entries = await widget.api.marketingEntries(section.name);
    if (mounted) setState(() => _marketing[section] = entries);
  }

  Future<void> _saveMarketing(MarketingSection section, Map<String, Object?> payload) async {
    if (!_canViewManagement) return;
    await _run(() async {
      await widget.api.saveMarketing(section.name, payload);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Alteração salva.')),
      );
      await _loadMarketing(section);
    });
  }

  Widget _marketingView(MarketingSection section) => MarketingView(
    section: section,
    entries: _marketing[section],
    busy: _busy,
    canEdit: _canViewManagement,
    refresh: _refreshSection,
    save: (payload) => _saveMarketing(section, payload),
  );

  Future<void> _loadAdminUsers() async {
    final users = await widget.api.adminUsers();
    if (mounted) setState(() => _adminUsers = users);
  }

  Future<void> _loadAudit(DateTimeRange? period) async {
    await _run(() async {
      final events = await widget.api.auditEvents(period?.start, period?.end);
      if (!mounted) return;
      setState(() {
        _auditPeriod = period;
        _auditEvents = events;
      });
    });
  }

  Future<void> _loadDeliveries() async {
    final orders = await widget.api.deliveries();
    if (mounted) setState(() => _deliveries = orders);
  }

  Future<void> _loadDeliveryUsers() async {
    final tenant = _tenant;
    if (tenant == null) return;
    final users = await widget.api.deliveryUsers(tenant);
    if (mounted) setState(() => _deliveryUsers = users);
  }

  Future<void> _advanceDelivery(int id, bool complete) async {
    await _run(() async {
      await widget.api.advanceDelivery(id, complete: complete);
      await _loadDeliveries();
    });
  }

  Future<void> _loadFinance(DateTimeRange range) async {
    await _run(() async {
      final data = await widget.api.finance(range.start, range.end);
      if (!mounted) return;
      setState(() {
        _financePeriod = range;
        _finance = data;
      });
    });
  }

  Future<void> _loadReports(DateTimeRange range) async {
    await _run(() async {
      final data = await widget.api.reports(range.start, range.end);
      if (!mounted) return;
      setState(() {
        _reportsPeriod = range;
        _reports = data;
      });
    });
  }

  Future<void> _loadInventory(DateTimeRange range) async {
    await _run(() async {
      final inventory = await widget.api.inventory(range.start, range.end);
      if (!mounted) return;
      setState(() {
        _inventoryPeriod = range;
        _inventoryItems = inventory.items;
        _inventoryMovements = inventory.movements;
      });
    });
  }

  Future<void> _loadCustomers(int page, String search) async {
    await _run(() async {
      final result = await widget.api.customers(page, search);
      if (!mounted) return;
      setState(() {
        _customerSearch = search;
        _customerPage = page;
        _customerTotal = result.total;
        _customers = result.items;
      });
    });
  }

  Future<void> _showCustomer(int id) async {
    Map<String, dynamic>? customer;
    await _run(() async {
      customer = await widget.api.customer(id);
    });
    if (!mounted || customer == null) return;
    await Navigator.of(context).push<void>(
      MaterialPageRoute(builder: (context) =>
          CustomerHistoryView(customer: customer!, orderStatus: _status)),
    );
  }

  Future<void> _refreshSection() async {
    switch (_section) {
      case 0:
        await _run(_loadDashboard);
      case 1:
        await _refresh();
      case 2:
        await _run(_loadKitchen);
      case 3:
        await _run(_loadMenu);
      case 4:
        await _loadInventory(_inventoryPeriod);
      case 5:
        await _loadCustomers(_customerPage, _customerSearch);
      case 6:
        await _loadFinance(_financePeriod);
      case 7:
        await _loadReports(_reportsPeriod);
      case 8:
        await _run(_loadDeliveries);
      case 9:
        await _run(_loadDeliveryUsers);
      case 10:
        await _run(_loadAdminUsers);
      case 11:
        await _loadAudit(_auditPeriod);
      case >= 12 && <= 14:
        final section = MarketingSection.values[_section - 12];
        await _run(() => _loadMarketing(section));
      case 15:
        await _run(_loadWazza);
      case 16:
        await _run(_loadWhatsApp);
      case 17:
        await _run(_loadCatalogPreview);
    }
  }

  Future<void> _loadKitchen() async {
    final orders = await widget.api.kitchenOrders(_kitchenArea);
    if (mounted) setState(() => _kitchenOrders = orders);
  }

  Future<void> _loadCatalogPreview() async {
    final preview = await widget.api.catalogPreview(_store.text.trim().toLowerCase());
    if (preview['tenant_id'] != _tenant) throw const ManagementApiError(403);
    if (mounted) setState(() => _catalogPreview = preview);
  }

  Widget _previewView() => StorefrontPreview(
    data: _catalogPreview,
    origin: widget.api.origin,
    busy: _busy,
    refresh: _refreshSection,
    edit: _canViewManagement ? _showAppearanceEditor : null,
  );

  Future<void> _showAppearanceEditor() async {
    if (_busy || !_canViewManagement || _tenant == null) return;
    Map<String, dynamic>? settings;
    await _run(() async {
      settings = await widget.api.catalogAppearance();
    });
    if (!mounted || settings == null || _tenant == null) return;
    final published = _catalogPreview?['public_settings'];
    final current = {
      ...settings!,
      if (published is Map<String, dynamic>)
        for (final entry in published.entries)
          if (entry.value != null) entry.key: entry.value,
    };
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      isDismissible: false,
      enableDrag: false,
      builder: (_) => AppearanceEditor(current: current, save: _saveAppearance),
    );
  }

  Future<bool> _saveAppearance(Map<String, Object?> settings) async {
    if (!_canViewManagement || _tenant == null) return false;
    var saved = false;
    await _run(() async {
      await widget.api.updateCatalogAppearance(settings);
      saved = true;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Aparência publicada.')),
      );
      await _loadCatalogPreview();
    });
    return saved;
  }

  void _showCatalogEditor({required bool product, Map<String, dynamic>? current}) {
    if (_busy || !_canViewManagement || _tenant == null) return;
    final tenant = _tenant!;
    showModalBottomSheet<void>(
      context: context, isScrollControlled: true, useSafeArea: true,
      backgroundColor: Colors.white,
      showDragHandle: true, isDismissible: false, enableDrag: false,
      builder: (_) => CatalogEditor(
        categories: _categories,
        current: current,
        mediaOrigin: widget.api.origin,
        saveCategory: product ? null : (name, active) => _saveCatalog(() => current == null
          ? widget.api.createCategory(tenant, name)
          : widget.api.updateCategory(current['id'] as int, name, active)),
        saveProduct: !product ? null : (draft) => _saveCatalog(() => widget.api.saveCatalogItem(
          tenant, id: current?['id'] as int?, name: draft.name, priceCents: draft.priceCents,
          description: draft.description, categoryId: draft.categoryId, photo: draft.photo,
        )),
      ),
    );
  }

  Future<void> _deleteCategory(Map<String, dynamic> category) async {
    if (_busy || !_canViewManagement || _tenant == null || category['id'] is! int) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Excluir ${category['name']}?'),
        content: const Text(
          'A categoria e seus produtos deixam de aparecer no cardápio publicado. '
          'Os produtos continuam cadastrados e a categoria pode ser reativada.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Voltar')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Excluir categoria')),
        ],
      ),
    );
    if (mounted && confirmed == true) {
      await _saveCatalog(() => widget.api.deleteCategory(category['id'] as int));
    }
  }

  Future<void> _toggleProduct(Map<String, dynamic> item) async {
    final tenant = _tenant;
    final id = item['id'];
    if (tenant == null || id is! int || !_canViewManagement) return;
    await _saveCatalog(() => widget.api.setCatalogItemActive(tenant, id, item['active'] == false));
  }

  Future<bool> _saveCatalog(Future<void> Function() create) async {
    if (_tenant == null || !_canViewManagement) return false;
    var saved = false;
    await _run(() async {
      await create();
      saved = true;
      if (!mounted) return;
      setState(() => _catalogPreview = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cardápio atualizado.')),
      );
      await _loadMenu();
    });
    return saved;
  }

  Future<void> _loadMenu() async {
    final menu = await widget.api.menu();
    if (mounted) {
      setState(() {
        _categories = menu.categories;
        _menuItems = menu.items;
      });
    }
  }

  Future<void> _changeKitchenArea(String area) async {
    if (_busy || area == _kitchenArea) return;
    setState(() {
      _kitchenArea = area;
      _kitchenOrders = [];
    });
    await _run(_loadKitchen);
  }

  Future<void> _advanceKitchenOrder(int id, bool ready) async {
    await _run(() async {
      await widget.api.advanceKitchenOrder(id, _kitchenArea, ready: ready);
      await _loadKitchen();
    });
  }

  Future<void> _loadOrders(int tenant, int page, {bool summary = false, bool applyFilters = true}) async {
    final filters = applyFilters
        ? (customer: _customer.text.trim(), number: _numberFilter.text.trim(), status: _statusFilter)
        : _appliedFilters;
    final orders = await widget.api.orders(
      tenant,
      page: page,
      customer: filters.customer,
      number: filters.number,
      status: filters.status,
    );
    if (!mounted) return;
    setState(() {
      _orders = orders.items;
      _totalOrders = orders.total;
      _page = page;
      _appliedFilters = filters;
    });
    if (summary) {
      final counts = await widget.api.orderSummary(tenant);
      if (mounted) setState(() => _summary = counts);
    }
  }

  Future<void> _refresh({int? page, bool summary = true}) async {
    final tenant = _tenant;
    if (tenant == null) return;
    await _run(() => _loadOrders(tenant, page ?? 1, summary: summary, applyFilters: page == null));
  }

  Future<void> _logout() async {
    await _run(() async {
      try {
        await widget.api.logout();
      } finally {
        if (mounted) {
          setState(() {
            _tenant = null;
          _clearManagementData();
            _orders = [];
          _dashboard = {};
          _kitchenOrders = [];
          _categories = [];
          _menuItems = [];
          });
        }
      }
    });
  }

  String? _required(String? value) => value == null || value.trim().isEmpty
      ? 'Preencha este campo.'
      : null;

  @override
  Widget build(BuildContext context) {
    final isSignedIn = _tenant != null;
    return Scaffold(
      backgroundColor: const Color(0xfff8fafc),
      appBar: isSignedIn ? AppBar(
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xff0f172a),
        title: Image.asset('assets/fomizero-logo.png', width: 132, semanticLabel: 'Fomizero'),
        actions: isSignedIn
            ? [
                IconButton(onPressed: _busy ? null : _refreshSection, icon: const Icon(Icons.refresh), tooltip: 'Atualizar'),
                TextButton(onPressed: _busy ? null : _logout, child: const Text('Sair', style: TextStyle(color: Color(0xff0f172a)))),
              ]
            : null,
      ) : null,
      bottomNavigationBar: isSignedIn
          ? NavigationBar(
              backgroundColor: Colors.white,
              selectedIndex: _section >= 4 ? 4 : _section,
              onDestinationSelected: (index) {
                if (index == 4) {
                  _showMore();
                } else {
                  _selectSection(index);
                }
              },
              destinations: [
                const NavigationDestination(icon: Icon(Icons.grid_view_outlined), label: 'Início'),
                const NavigationDestination(icon: Icon(Icons.shopping_bag_outlined), label: 'Pedidos'),
                const NavigationDestination(icon: Icon(Icons.local_fire_department_outlined), label: 'Cozinha'),
                const NavigationDestination(icon: Icon(Icons.restaurant_menu), label: 'Cardápio'),
                const NavigationDestination(icon: Icon(Icons.apps), label: 'Mais'),
              ],
            )
          : null,
      body: SafeArea(
        child: Column(
          children: [
            if (_busy) const LinearProgressIndicator(),
            if (_error case final error?)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            Expanded(
              child: !isSignedIn ? _loginView() : switch (_section) {
                0 => DashboardView(
                  data: _dashboard,
                  period: _period,
                  customRange: _customRange,
                  busy: _busy,
                  refresh: _refreshSection,
                  onPeriodChanged: _changePeriod,
                  onOrders: () => _selectSection(1),
                  onKitchen: () => _selectSection(2),
                  onCatalog: () => _selectSection(3),
                  orderStatus: _status,
                ),
                2 => KitchenView(
                  orders: _kitchenOrders,
                  area: _kitchenArea,
                  onArea: _changeKitchenArea,
                  refresh: _refreshSection,
                  onAdvance: _advanceKitchenOrder,
                  busy: _busy,
                ),
                3 => CatalogView(
                  mediaOrigin: widget.api.origin,
                  onAddCategory: _canViewManagement ? () => _showCatalogEditor(product: false) : null,
                  onAddProduct: _canViewManagement ? () => _showCatalogEditor(product: true) : null,
                  onEditCategory: _canViewManagement ? (category) => _showCatalogEditor(product: false, current: category) : null,
                  onDeleteCategory: _canViewManagement ? _deleteCategory : null,
                  onEditProduct: _canViewManagement ? (item) => _showCatalogEditor(product: true, current: item) : null,
                  onProductAvailability: _canViewManagement ? _toggleProduct : null,
                  categories: _categories,
                  items: _menuItems,
                  refresh: _refreshSection,
                  busy: _busy,
                ),
                4 => InventoryView(
                  items: _inventoryItems,
                  movements: _inventoryMovements,
                  period: _inventoryPeriod,
                  busy: _busy,
                  refresh: _refreshSection,
                  onPeriod: _loadInventory,
                ),
                5 => CustomersView(
                  customers: _customers,
                  total: _customerTotal,
                  page: _customerPage,
                  search: _customerSearch,
                  busy: _busy,
                  onSearch: (search) => _loadCustomers(1, search.trim()),
                  onPage: (page) => _loadCustomers(page, _customerSearch),
                  onCustomer: _showCustomer,
                  refresh: _refreshSection,
                ),
                6 => FinanceView(
                  summary: _finance?.summary,
                  movements: _finance?.movements,
                  period: _financePeriod,
                  busy: _busy,
                  refresh: _refreshSection,
                  onPeriod: _loadFinance,
                ),
                7 => ReportsView(
                  summary: _reports?.summary,
                  items: _reports?.items,
                  lowStock: _reports?.lowStock,
                  period: _reportsPeriod,
                  busy: _busy,
                  refresh: _refreshSection,
                  onPeriod: _loadReports,
                ),
                8 => DeliveriesView(
                  orders: _deliveries,
                  busy: _busy,
                  refresh: _refreshSection,
                  onAdvance: _advanceDelivery,
                ),
                9 => DeliveryUsersView(users: _deliveryUsers, refresh: _refreshSection),
                10 => AdminUsersView(users: _adminUsers, refresh: _refreshSection),
                11 => AuditView(
                  events: _auditEvents,
                  period: _auditPeriod,
                  busy: _busy,
                  refresh: _refreshSection,
                  onPeriod: _loadAudit,
                ),
                >= 12 && <= 14 => _marketingView(MarketingSection.values[_section - 12]),
                15 => WazzaView(
                  connection: _wazzaConnection,
                  requests: _wazzaRequests,
                  busy: _busy,
                  refresh: _refreshSection,
                  previous: _wazzaCursors.length <= 1 ? null :
                    () => _run(() => _loadWazzaPage(_wazzaCursors.sublist(0, _wazzaCursors.length - 1))),
                  next: _wazzaNext == null ? null :
                    () => _run(() => _loadWazzaPage([..._wazzaCursors, _wazzaNext])),
                  decide: _decideWazza,
                ),
                16 => WhatsAppActivityView(logs: _whatsappLogs, refresh: _refreshSection),
                17 => _previewView(),
                _ => _ordersView(),
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _loginView() => DecoratedBox(
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xfffff1f2), Colors.white, Color(0xfff1f5f9)],
      ),
    ),
    child: LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: (constraints.maxHeight - 32).clamp(0.0, double.infinity).toDouble()),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 448),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _form,
                    child: AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Center(child: Image.asset('assets/fomizero-logo.png', width: 170, semanticLabel: 'Fomizero')),
                          const SizedBox(height: 12),
                          Text('Bem-vindo ao Fomizero', textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
                          const SizedBox(height: 4),
                          const Text('Faça login para acessar sua loja.', textAlign: TextAlign.center),
                          const SizedBox(height: 24),
                          TextFormField(
                            controller: _store,
                            enabled: !_busy,
                            validator: _required,
                            autocorrect: false,
                            decoration: const InputDecoration(labelText: 'Identificador da loja', border: OutlineInputBorder()),
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _email,
                            enabled: !_busy,
                            validator: _required,
                            autofillHints: const [AutofillHints.username],
                            keyboardType: TextInputType.emailAddress,
                            decoration: const InputDecoration(labelText: 'Email', hintText: 'admin@empresa.com', border: OutlineInputBorder()),
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _password,
                            enabled: !_busy,
                            validator: _required,
                            autofillHints: const [AutofillHints.password],
                            obscureText: true,
                            autocorrect: false,
                            enableSuggestions: false,
                            onFieldSubmitted: (_) => _login(),
                            decoration: const InputDecoration(labelText: 'Senha', border: OutlineInputBorder()),
                          ),
                          const SizedBox(height: 20),
                          FilledButton(
                            onPressed: _busy ? null : _login,
                            child: Text(_busy ? 'Entrando…' : 'Entrar'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );

  String _status(Map<String, dynamic> order) =>
      switch (order['status']?.toString().trim().toUpperCase()) {
        'RECEBIDO' || 'RECEIVED' || 'PENDING' => 'Recebido',
        'CONFIRMADO' || 'CONFIRMED' => 'Confirmado',
        'EM_PREPARO' || 'PREPARANDO' || 'PREPARING' => 'Em preparo',
        'PRONTO' || 'READY' || 'READY_FOR_DELIVERY' => 'Pronto',
        'DRIVER_ASSIGNED' || 'ASSIGNED' => 'Entregador designado',
        'OUT_FOR_DELIVERY' || 'SAIU_PARA_ENTREGA' || 'IN_TRANSIT' => 'Saiu para entrega',
        'ENTREGUE' || 'DELIVERED' => 'Entregue',
        'CONCLUIDO' || 'COMPLETED' => 'Concluído',
        'CANCELADO' || 'CANCELLED' || 'CANCELED' => 'Cancelado',
        'FAILED' => 'Falhou',
        _ => 'Status indisponível',
      };

  String _number(Map<String, dynamic> order) =>
      '#${order['daily_order_number'] ?? order['id']}';

  String? _total(Map<String, dynamic> order) {
    final cents = order['total_cents'];
    final total = cents is num ? cents / 100 : order['valor_total'];
    return total is num
        ? 'R\$ ${total.toStringAsFixed(2).replaceAll('.', ',')}'
        : null;
  }

  void _showOrder(Map<String, dynamic> order) {
    final items = order['itens'] is List ? (order['itens'] as List).whereType<Map>() : const <Map>[];
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => SafeArea(
        top: false,
        child: FractionallySizedBox(
          heightFactor: .92,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Pedido'),
                        Text(_number(order), style: Theme.of(context).textTheme.headlineSmall),
                      ],
                    ),
                  ),
                  Chip(label: Text(_status(order))),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close),
                    tooltip: 'Fechar detalhes',
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _detailPanel('Cliente', Icons.person_outline, [
                order['customer_name']?.toString() ?? 'Cliente',
                if (order['customer_phone'] case final String phone when phone.isNotEmpty) phone,
              ]),
              _detailPanel('Entrega', Icons.location_on_outlined, [
                if (order['tipo_entrega'] case final String delivery when delivery.isNotEmpty) delivery,
                if (order['endereco'] case final String address when address.isNotEmpty) address,
              ]),
              _detailPanel('Pagamento', Icons.credit_card, [
                if (order['forma_pagamento'] case final String payment when payment.isNotEmpty) payment,
              ]),
              _detailPanel('Itens', Icons.restaurant_menu, [
                for (final item in items)
                  '${item['qtd'] ?? item['quantity'] ?? 1} × ${item['nome'] ?? item['name'] ?? 'Item'}',
              ]),
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: const Color(0xff0f172a),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: ListTile(
                    textColor: Colors.white,
                    title: const Text('Total'),
                    trailing: Text(_total(order) ?? '—', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  ),
                ),
              ),
              if (order['observacao'] case final String note when note.isNotEmpty)
                _detailPanel('Observação', Icons.notes, [note]),
            ],
          ),
        ),
      ),
    );
  }

  Widget _detailPanel(String title, IconData icon, List<String> lines) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 18, color: const Color(0xff64748b)),
            const SizedBox(width: 8),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 8),
          if (lines.isEmpty) const Text('—'),
          for (final line in lines)
            Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(line)),
        ],
      ),
    ),
  );

  Widget _ordersView() {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(18, 24, 18, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Pedidos', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 6),
                  const Text('Acompanhe os pedidos da sua loja.'),
                  const SizedBox(height: 16),
                  if (_summary.isNotEmpty) ...[
                    SizedBox(
                      height: 100,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          for (final (key, label, icon) in const [
                            ('today', 'Pedidos hoje', Icons.shopping_bag_outlined),
                            ('pending', 'Pendentes', Icons.schedule),
                            ('preparing', 'Em preparo', Icons.timer_outlined),
                            ('delivering', 'Em entrega', Icons.local_shipping_outlined),
                            ('completed', 'Concluídos', Icons.check_circle_outline),
                          ])
                            Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: SizedBox(
                                width: 168,
                                child: ManagementMetric(label, '${_summary[key] ?? 0}', icon),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  TextField(
                    controller: _customer,
                    enabled: !_busy,
                    decoration: const InputDecoration(labelText: 'Cliente', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _refresh(summary: false),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _numberFilter,
                    enabled: !_busy,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Número do pedido', border: OutlineInputBorder()),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _refresh(summary: false),
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    initialValue: _statusFilter,
                    decoration: const InputDecoration(labelText: 'Status', border: OutlineInputBorder()),
                    items: [
                      const DropdownMenuItem(value: '', child: Text('Todos os status')),
                      for (final status in const [
                        'PENDING', 'CONFIRMADO', 'EM_PREPARO', 'PRONTO',
                        'DRIVER_ASSIGNED', 'SAIU_PARA_ENTREGA', 'ENTREGUE',
                        'CANCELADO', 'FAILED',
                      ])
                        DropdownMenuItem(value: status, child: Text(_status({'status': status}))),
                    ],
                    onChanged: _busy ? null : (value) => setState(() => _statusFilter = value ?? ''),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.tonalIcon(
                    onPressed: _busy ? null : () => _refresh(summary: false),
                    icon: const Icon(Icons.filter_list),
                    label: const Text('Filtrar pedidos'),
                  ),
                ],
              ),
            ),
          ),
          if (_orders.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Center(child: Text(_busy ? 'Carregando pedidos…' : 'Nenhum pedido nesta lista.')),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 20),
              sliver: SliverList.builder(
                itemCount: _orders.length,
                itemBuilder: (context, index) {
                  final order = _orders[index];
                  return Card(
                    color: Colors.white,
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      onTap: () => _showOrder(order),
                      contentPadding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
                      title: Text('Pedido ${_number(order)}', style: const TextStyle(fontWeight: FontWeight.w700)),
                      subtitle: Text([
                        order['customer_name']?.toString() ?? 'Cliente',
                        _status(order),
                        if (_total(order) case final total?) total,
                      ].join(' · ')),
                      trailing: const Icon(Icons.chevron_right),
                    ),
                  );
                },
              ),
            ),
          if (_totalOrders > 8 || _page > 1)
            SliverToBoxAdapter(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    tooltip: 'Página anterior',
                    onPressed: _busy || _page <= 1 ? null : () => _refresh(page: _page - 1, summary: false),
                    icon: const Icon(Icons.chevron_left),
                  ),
                  Text('Página $_page de ${(_totalOrders / 8).ceil().clamp(1, 125000)}'),
                  IconButton(
                    tooltip: 'Próxima página',
                    onPressed: _busy || _page * 8 >= _totalOrders ? null : () => _refresh(page: _page + 1, summary: false),
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
