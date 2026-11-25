import 'package:flutter/material.dart';

class LoginView extends StatefulWidget {
  const LoginView({
    super.key,
    required this.formKey,
    required this.store,
    required this.email,
    required this.password,
    required this.validator,
    required this.onSubmit,
    required this.busy,
    required this.error,
    this.onForgotPassword,
    this.onCreateAccount,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController store;
  final TextEditingController email;
  final TextEditingController password;
  final FormFieldValidator<String> validator;
  final VoidCallback onSubmit;
  final bool busy;
  final String? error;
  final VoidCallback? onForgotPassword;
  final VoidCallback? onCreateAccount;

  @override
  State<LoginView> createState() => _LoginViewState();
}

class _LoginViewState extends State<LoginView> {
  static const _ink = Color(0xff151923);
  static const _muted = Color(0xff526071);
  static const _line = Color(0xffe2e8f0);
  static const _red = Color(0xffdc2626);
  bool _showPassword = false;

  @override
  Widget build(BuildContext context) {
    final typography = Theme.of(context).textTheme;
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xffffeef0), Color(0xfffafafa), Color(0xffeef3f9)],
        ),
      ),
      child: LayoutBuilder(
        builder: (context, size) => SingleChildScrollView(
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: (size.maxHeight - 48).clamp(0.0, double.infinity),
            ),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 416),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    border: Border.all(color: _line),
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x140f172a),
                        blurRadius: 32,
                        offset: Offset(0, 14),
                      ),
                    ],
                  ),
                  child: Padding(
                    padding: EdgeInsets.all(size.maxWidth < 360 ? 20 : 28),
                    child: Form(
                      key: widget.formKey,
                      child: AutofillGroup(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Center(
                              child: Image.asset(
                                'assets/fomizero-logo.png',
                                width: 148,
                                semanticLabel: 'Fomizero',
                              ),
                            ),
                            const SizedBox(height: 22),
                            Text(
                              'Acesse sua loja',
                              textAlign: TextAlign.center,
                              style: typography.headlineSmall?.copyWith(
                                color: _ink,
                                fontWeight: FontWeight.w800,
                                letterSpacing: -0.65,
                              ),
                            ),
                            const SizedBox(height: 5),
                            const Text(
                              'Entre com a conta do painel do restaurante.',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: _muted, height: 1.4),
                            ),
                            const SizedBox(height: 22),
                            if (widget.error case final error?) ...[
                              _errorMessage(error),
                              const SizedBox(height: 16),
                            ],
                            TextFormField(
                              controller: widget.store,
                              enabled: !widget.busy,
                              validator: widget.validator,
                              autocorrect: false,
                              enableSuggestions: false,
                              textInputAction: TextInputAction.next,
                              decoration: _decoration(
                                'Identificador da loja',
                                Icons.storefront_outlined,
                                hint: 'Ex.: meuburger',
                              ),
                            ),
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: widget.email,
                              enabled: !widget.busy,
                              validator: widget.validator,
                              autofillHints: const [AutofillHints.username],
                              keyboardType: TextInputType.emailAddress,
                              textInputAction: TextInputAction.next,
                              autocorrect: false,
                              decoration: _decoration(
                                'E-mail',
                                Icons.mail_outline_rounded,
                              ),
                            ),
                            const SizedBox(height: 14),
                            TextFormField(
                              controller: widget.password,
                              enabled: !widget.busy,
                              validator: widget.validator,
                              autofillHints: const [AutofillHints.password],
                              obscureText: !_showPassword,
                              autocorrect: false,
                              enableSuggestions: false,
                              textInputAction: TextInputAction.done,
                              onFieldSubmitted: (_) {
                                if (!widget.busy) widget.onSubmit();
                              },
                              decoration: _decoration(
                                'Senha',
                                Icons.lock_outline_rounded,
                                trailing: IconButton(
                                  tooltip: _showPassword
                                      ? 'Ocultar senha'
                                      : 'Mostrar senha',
                                  onPressed: widget.busy
                                      ? null
                                      : () => setState(
                                          () => _showPassword = !_showPassword,
                                        ),
                                  icon: Icon(
                                    _showPassword
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined,
                                  ),
                                ),
                              ),
                            ),
                            if (widget.onForgotPassword != null)
                              Align(
                                alignment: Alignment.centerRight,
                                child: TextButton(
                                  onPressed: widget.busy
                                      ? null
                                      : widget.onForgotPassword,
                                  child: const Text('Esqueci minha senha'),
                                ),
                              ),
                            const SizedBox(height: 22),
                            FilledButton.icon(
                              onPressed: widget.busy ? null : widget.onSubmit,
                              style: FilledButton.styleFrom(
                                backgroundColor: _red,
                                foregroundColor: Colors.white,
                                minimumSize: const Size.fromHeight(54),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                textStyle: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              icon: widget.busy
                                  ? const SizedBox.square(
                                      dimension: 17,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : const Icon(
                                      Icons.arrow_forward_rounded,
                                      size: 19,
                                    ),
                              iconAlignment: IconAlignment.end,
                              label: Text(widget.busy ? 'Entrando…' : 'Entrar'),
                            ),
                            if (widget.onCreateAccount != null) ...[
                              const SizedBox(height: 16),
                              const Divider(height: 1, color: _line),
                              const SizedBox(height: 13),
                              const Text(
                                'Ainda não tem loja?',
                                textAlign: TextAlign.center,
                                style: TextStyle(color: _muted),
                              ),
                              OutlinedButton(
                                onPressed: widget.busy
                                    ? null
                                    : widget.onCreateAccount,
                                child: const Text('Criar minha loja'),
                              ),
                            ],
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
  }

  InputDecoration _decoration(
    String label,
    IconData icon, {
    String? hint,
    Widget? trailing,
  }) {
    final outline = OutlineInputBorder(
      borderRadius: BorderRadius.circular(13),
      borderSide: const BorderSide(color: _line),
    );
    return InputDecoration(
      labelText: label,
      hintText: hint,
      filled: true,
      fillColor: const Color(0xfff8fafc),
      prefixIcon: Icon(icon, size: 20),
      prefixIconColor: _muted,
      suffixIcon: trailing,
      suffixIconColor: _muted,
      border: outline,
      enabledBorder: outline,
      focusedBorder: outline.copyWith(
        borderSide: const BorderSide(color: _red, width: 1.4),
      ),
      disabledBorder: outline,
    );
  }

  Widget _errorMessage(String text) => Semantics(
    liveRegion: true,
    child: DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xfffff1f2),
        border: Border.all(color: const Color(0xfffecdd3)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(
              Icons.info_outline_rounded,
              size: 19,
              color: Color(0xff9f1239),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: const TextStyle(color: Color(0xff9f1239)),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
