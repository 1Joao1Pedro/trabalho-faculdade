const apiBase = `${window.location.protocol}//${window.location.hostname}:8001`;
const $ = (selector) => document.querySelector(selector);
let csrfToken = "";
let loginMode = false;
let currentUser = null;

async function api(path, options = {}) {
    const method = options.method || "GET";
    const response = await fetch(`${apiBase}/api${path}`, {
        ...options,
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            ...(method !== "GET" ? { "X-CSRF-Token": csrfToken } : {}),
            ...options.headers,
        },
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
        throw new Error(detail || "Não foi possível concluir a operação.");
    }
    return data;
}

function message(text, error = false) {
    const box = $("#message");
    box.textContent = text;
    box.className = `mb-5 rounded-xl px-4 py-3 text-sm ${error ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800"}`;
}

function show(view) {
    ["welcome", "auth", "profile", "admin"].forEach((name) => $(`#${name}-view`).classList.toggle("hidden", name !== view));
}

function showAuth(login = false) {
    loginMode = login;
    $("#auth-title").textContent = login ? "Entrar" : "Criar conta";
    $("#auth-submit").textContent = login ? "Entrar" : "Criar conta";
    $("#name-field").classList.toggle("hidden", login);
    $("#confirmation-field").classList.toggle("hidden", login);
    $("#auth-form").elements.password_confirmation.required = !login;
    $("#auth-form").elements.password.autocomplete = login ? "current-password" : "new-password";
    $("#switch-auth").textContent = login ? "Ainda não tenho uma conta" : "Já tenho uma conta";
    show("auth");
}

function signedIn(user) {
    currentUser = user;
    $("#nav-login").classList.add("hidden");
    $("#nav-register").classList.add("hidden");
    $("#nav-logout").classList.remove("hidden");
    if (user.role === "admin" || user.role === "superuser") {
        const isSuperuser = user.role === "superuser";
        $("#role-label").textContent = isSuperuser ? "Superusuário · somente consulta" : "Administração";
        $("#users-title").textContent = isSuperuser ? "Todos os cadastros" : "Usuários";
        $("#history-button").classList.toggle("hidden", isSuperuser);
        show("admin");
        loadUsers();
    } else {
        $("#profile-form").elements.name.value = user.name;
        $("#profile-form").elements.email.value = user.email;
        $("#profile-form").elements.password.value = "";
        show("profile");
    }
}

function signedOut() {
    currentUser = null;
    $("#nav-login").classList.remove("hidden");
    $("#nav-register").classList.remove("hidden");
    $("#nav-logout").classList.add("hidden");
    show("welcome");
}

function formValues(form) { return Object.fromEntries(new FormData(form).entries()); }

async function loadUsers() {
    try {
        const q = encodeURIComponent($("#search").value.trim());
        const endpoint = currentUser.role === "superuser" ? "/superuser/users" : "/admin/users";
        const users = await api(`${endpoint}?q=${q}`);
        const list = $("#users-list"); list.replaceChildren();
        for (const user of users) {
            const row = document.createElement("div"); row.className = "flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3";
            const name = document.createElement("span"); name.className = "text-sm"; name.textContent = `${user.name} · ${user.email}`;
            const controls = document.createElement("div"); controls.className = "flex gap-2";
            if (currentUser.role !== "superuser") {
                const edit = document.createElement("button"); edit.className = "rounded-lg border px-3 py-1.5 text-sm"; edit.textContent = "Editar"; edit.onclick = () => editUser(user); controls.append(edit);
                const del = document.createElement("button"); del.className = "rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-700"; del.textContent = "Excluir"; del.onclick = async () => { if (confirm(`Excluir ${user.name}?`)) try { await api(`/admin/users/${user.id}`, { method: "DELETE" }); message("Usuário excluído."); loadUsers(); } catch (e) { message(e.message, true); } }; controls.append(del);
            }
            row.append(name, controls); list.append(row);
        }
    } catch (error) { message(error.message, true); }
}

async function editUser(user) {
    const name = prompt("Nome", user.name); if (name === null) return;
    const email = prompt("E-mail", user.email); if (email === null) return;
    try { await api(`/admin/users/${user.id}`, { method: "PUT", body: JSON.stringify({ name, email, password: null }) }); message("Usuário atualizado."); loadUsers(); }
    catch (error) { message(error.message, true); }
}

$("#nav-login").onclick = () => showAuth(true);
$("#nav-register").onclick = $("#hero-register").onclick = () => showAuth(false);
$("#switch-auth").onclick = () => showAuth(!loginMode);
$("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formValues(event.currentTarget);
    try {
        if (loginMode) { const result = await api("/login", { method: "POST", body: JSON.stringify(data) }); message("Login realizado."); signedIn(result.user); }
        else {
            if (data.password !== data.password_confirmation) throw new Error("A confirmação da senha não confere.");
            const user = await api("/register", { method: "POST", body: JSON.stringify(data) }); message("Conta criada com sucesso."); signedIn(user);
        }
    } catch (error) { message(error.message, true); }
});

$("#profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formValues(event.currentTarget); if (!data.password) data.password = null;
    try { const user = await api("/me", { method: "PUT", body: JSON.stringify(data) }); message("Dados atualizados."); signedIn(user); }
    catch (error) { message(error.message, true); }
});

$("#nav-logout").onclick = async () => { try { await api("/logout", { method: "POST", body: "{}" }); signedOut(); message("Você saiu da sua conta."); } catch (error) { message(error.message, true); } };
$("#search-button").onclick = loadUsers;
$("#search").onkeydown = (event) => { if (event.key === "Enter") loadUsers(); };
$("#history-button").onclick = async () => {
    const list = $("#history-list"); list.classList.toggle("hidden"); if (list.classList.contains("hidden")) return;
    try {
        const logs = await api("/admin/audit"); list.replaceChildren();
        for (const log of logs) { const row = document.createElement("div"); row.className = "rounded-xl border border-slate-200 p-3 text-sm"; row.textContent = `${log.action} · ${log.description} · ${new Date(log.created_at).toLocaleString("pt-BR")}`; list.append(row); }
    } catch (error) { message(error.message, true); }
};

(async () => {
    try {
        const token = await fetch(`${apiBase}/api/csrf`, { credentials: "include" }).then((r) => r.json());
        csrfToken = token.csrf_token;
        try { signedIn(await api("/me")); } catch { signedOut(); }
    } catch { signedOut(); message("Não foi possível conectar ao servidor Python.", true); }
})();
