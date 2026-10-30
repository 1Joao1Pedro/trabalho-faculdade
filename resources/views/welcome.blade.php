<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>trabalho faculdade</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100 text-slate-800 antialiased">
    <header class="border-b border-slate-200 bg-white">
        <nav class="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
            <a href="/" class="text-lg font-bold text-teal-800">trabalho faculdade</a>
            <div class="flex items-center gap-3 text-sm">
                <button id="nav-login" class="rounded-lg px-3 py-2 hover:bg-slate-100">Entrar</button>
                <button id="nav-register" class="rounded-lg bg-teal-700 px-4 py-2 font-semibold text-white hover:bg-teal-800">Criar conta</button>
                <button id="nav-logout" class="hidden rounded-lg border px-3 py-2 hover:bg-slate-100">Sair</button>
            </div>
        </nav>
    </header>
    <main class="mx-auto max-w-5xl px-5 py-10">
        <div id="message" class="mb-5 hidden rounded-xl px-4 py-3 text-sm" role="status"></div>
        <section id="welcome-view" class="rounded-3xl bg-white p-8 shadow-sm md:p-14">
            <h1 class="max-w-2xl text-4xl font-bold tracking-tight md:text-5xl">Crie sua conta.</h1>
            <button id="hero-register" class="mt-8 rounded-xl bg-teal-700 px-6 py-3 font-semibold text-white hover:bg-teal-800">Começar cadastro</button>
        </section>
        <section id="auth-view" class="mx-auto hidden max-w-md rounded-2xl bg-white p-7 shadow-sm">
            <h1 id="auth-title" class="mb-6 text-2xl font-bold">Criar conta</h1>
            <form id="auth-form" class="space-y-4">
                <label id="name-field" class="block text-sm font-medium">Nome<input name="name" maxlength="100" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5" autocomplete="name"></label>
                <label class="block text-sm font-medium">E-mail<input name="email" type="email" required class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5" autocomplete="email"></label>
                <label class="block text-sm font-medium">Senha<input name="password" type="password" required minlength="8" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5" autocomplete="current-password"></label>
                <label id="confirmation-field" class="block text-sm font-medium">Confirmar senha<input name="password_confirmation" type="password" required minlength="8" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5" autocomplete="new-password"></label>
                <button id="auth-submit" class="w-full rounded-lg bg-teal-700 px-4 py-3 font-semibold text-white hover:bg-teal-800">Criar conta</button>
            </form>
            <button id="switch-auth" class="mt-4 text-sm text-teal-800 underline">Já tenho uma conta</button>
        </section>
        <section id="profile-view" class="mx-auto hidden max-w-xl rounded-2xl bg-white p-7 shadow-sm">
            <p class="text-xs font-bold uppercase tracking-widest text-teal-700">Minha conta</p><h1 class="mb-6 mt-1 text-2xl font-bold">Meus dados</h1>
            <form id="profile-form" class="space-y-4">
                <label class="block text-sm font-medium">Nome<input name="name" required maxlength="100" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5"></label>
                <label class="block text-sm font-medium">E-mail<input name="email" type="email" required class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5"></label>
                <label class="block text-sm font-medium">Nova senha <span class="font-normal text-slate-500">(opcional)</span><input name="password" type="password" minlength="8" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5"></label>
                <button class="rounded-lg bg-teal-700 px-5 py-2.5 font-semibold text-white">Salvar alterações</button>
            </form>
        </section>
        <section id="admin-view" class="hidden rounded-2xl bg-white p-7 shadow-sm">
            <p id="role-label" class="text-xs font-bold uppercase tracking-widest text-teal-700">Administração</p><h1 id="users-title" class="mb-5 mt-1 text-2xl font-bold">Cadastros</h1>
            <div class="mb-5 flex flex-wrap gap-2"><input id="search" placeholder="Buscar nome ou e-mail" class="min-w-52 flex-1 rounded-lg border border-slate-300 px-3 py-2"><button id="search-button" class="rounded-lg bg-teal-700 px-4 py-2 text-white">Buscar</button><button id="history-button" class="rounded-lg border px-4 py-2">Histórico</button></div>
            <div id="users-list" class="space-y-2"></div><div id="history-list" class="mt-5 hidden space-y-2"></div>
        </section>
    </main>
    <script src="{{ asset('app.js') }}?v=2" defer></script>
</body>
</html>
