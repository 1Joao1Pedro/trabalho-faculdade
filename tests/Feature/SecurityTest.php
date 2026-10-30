<?php

namespace Tests\Feature;

use App\Models\AuditLog;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class SecurityTest extends TestCase
{
    use RefreshDatabase;

    public function test_public_registration_hashes_password_and_cannot_create_an_administrator(): void
    {
        $this->post('/cadastro', ['name' => 'Maria Silva', 'email' => 'maria@example.com', 'password' => 'SenhaSegura123', 'password_confirmation' => 'SenhaSegura123', 'role' => 'admin'])->assertRedirect(route('profile.edit'));
        $user = User::where('email', 'maria@example.com')->firstOrFail();
        $this->assertSame('user', $user->role);
        $this->assertTrue(Hash::check('SenhaSegura123', $user->password));
        $this->assertAuthenticatedAs($user);
        $this->assertDatabaseHas('audit_logs', ['user_id' => $user->id, 'action' => 'user.created']);
        $this->assertStringNotContainsString('SenhaSegura123', AuditLog::first()->toJson());
    }

    public function test_registration_rejects_invalid_data_without_creating_a_user(): void
    {
        $this->post('/cadastro', ['name' => '', 'email' => 'invalido', 'password' => '123', 'password_confirmation' => '456'])->assertSessionHasErrors(['name', 'email', 'password']);
        $this->assertDatabaseCount('users', 0);
        $this->assertGuest();
    }

    public function test_duplicate_email_is_rejected(): void
    {
        $user = User::factory()->create();
        $this->post('/cadastro', ['name' => 'Outra pessoa', 'email' => $user->email, 'password' => 'SenhaSegura123', 'password_confirmation' => 'SenhaSegura123'])->assertSessionHasErrors(['email' => 'Este e-mail já está cadastrado.']);
        $this->assertDatabaseCount('users', 1);
    }

    public function test_invalid_login_is_denied_and_logged_without_credentials(): void
    {
        $user = User::factory()->create();
        $this->post('/login', ['email' => $user->email, 'password' => 'senha-incorreta'])->assertSessionHasErrors(['email' => 'E-mail ou senha incorretos.']);
        $this->assertGuest();
        $this->assertDatabaseHas('audit_logs', ['action' => 'login.failed', 'user_id' => null]);
        $this->assertStringNotContainsString('senha-incorreta', AuditLog::first()->toJson());
    }

    public function test_login_is_rate_limited_after_five_failures(): void
    {
        $user = User::factory()->create();
        for ($attempt = 0; $attempt < 5; $attempt++) {
            $this->post('/login', ['email' => $user->email, 'password' => 'wrong']);
        }
        $this->post('/login', ['email' => $user->email, 'password' => 'password'])->assertSessionHasErrors(['email' => 'Muitas tentativas. Aguarde um minuto antes de tentar novamente.']);
        $this->assertGuest();
    }

    public function test_successful_login_redirects_by_role_and_logs_access(): void
    {
        $admin = User::factory()->administrator()->create();
        $this->post('/login', ['email' => $admin->email, 'password' => 'password'])->assertRedirect(route('users.index'));
        $this->assertAuthenticatedAs($admin);
        $this->assertDatabaseHas('audit_logs', ['action' => 'login.success', 'user_id' => $admin->id]);
    }

    public function test_common_user_login_redirects_to_own_profile(): void
    {
        $user = User::factory()->create();
        $this->post('/login', ['email' => $user->email, 'password' => 'password'])->assertRedirect(route('profile.edit'));
        $this->assertAuthenticatedAs($user);
    }

    public function test_guests_cannot_access_protected_routes(): void
    {
        $user = User::factory()->create();
        foreach (['/perfil', '/admin/usuarios', '/admin/usuarios/'.$user->id.'/editar', '/admin/historico'] as $path) {
            $this->get($path)->assertRedirect(route('login'));
        }
        $this->put('/admin/usuarios/'.$user->id, ['name' => 'Alterado'])->assertRedirect(route('login'));
        $this->delete('/admin/usuarios/'.$user->id)->assertRedirect(route('login'));
        $this->assertModelExists($user);
    }

    public function test_common_user_cannot_access_any_administrator_operation_directly(): void
    {
        $viewer = User::factory()->create();
        $target = User::factory()->create(['name' => 'Original']);
        $this->actingAs($viewer);
        $this->get('/admin/usuarios')->assertForbidden()->assertSee('Acesso negado');
        $this->get('/admin/historico')->assertForbidden();
        $this->get('/admin/usuarios/'.$target->id.'/editar')->assertForbidden();
        $this->put('/admin/usuarios/'.$target->id, ['name' => 'Alterado', 'email' => 'changed@example.com'])->assertForbidden();
        $this->delete('/admin/usuarios/'.$target->id)->assertForbidden();
        $this->assertSame('Original', $target->fresh()->name);
        $this->assertDatabaseCount('users', 2);
        $this->assertDatabaseHas('audit_logs', ['user_id' => $viewer->id, 'action' => 'access.denied']);
    }

    public function test_profile_update_only_affects_current_user_and_ignores_privileged_fields(): void
    {
        $user = User::factory()->create();
        $other = User::factory()->create(['name' => 'Outra pessoa']);
        $this->actingAs($user)->put('/perfil', ['name' => 'Novo nome', 'email' => 'novo@example.com', 'id' => $other->id, 'role' => 'admin', 'password' => 'changed'])->assertRedirect(route('profile.edit'));
        $this->assertSame('user', $user->fresh()->role);
        $this->assertSame('Novo nome', $user->fresh()->name);
        $this->assertSame('Outra pessoa', $other->fresh()->name);
        $this->assertTrue(Hash::check('password', $user->fresh()->password));
        $this->assertDatabaseHas('audit_logs', ['action' => 'profile.updated', 'user_id' => $user->id]);
    }

    public function test_administrator_can_search_users_and_see_audit_history(): void
    {
        $admin = User::factory()->administrator()->create();
        User::factory()->create(['name' => 'Pessoa encontrada', 'email' => 'busca@example.com']);
        User::factory()->create(['name' => 'Pessoa ausente']);
        $this->actingAs($admin)->get('/admin/usuarios?q=busca@example.com')->assertOk()->assertSee('Pessoa encontrada')->assertDontSee('Pessoa ausente');
        AuditLog::factory()->create(['user_id' => $admin->id]);
        $this->get('/admin/historico')->assertOk()->assertSee('login.success');
    }

    public function test_administrator_can_update_a_user_and_operation_is_logged(): void
    {
        $admin = User::factory()->administrator()->create();
        $user = User::factory()->create();
        $this->actingAs($admin)->put('/admin/usuarios/'.$user->id, ['name' => 'Nome corrigido', 'email' => 'corrigido@example.com'])->assertRedirect(route('users.index'));
        $this->assertSame('Nome corrigido', $user->fresh()->name);
        $this->assertDatabaseHas('audit_logs', ['action' => 'user.updated', 'user_id' => $admin->id]);
    }

    public function test_invalid_update_does_not_change_data_or_log_success(): void
    {
        $admin = User::factory()->administrator()->create();
        $user = User::factory()->create(['name' => 'Original']);
        $this->actingAs($admin)->put('/admin/usuarios/'.$user->id, ['name' => '', 'email' => 'invalido'])->assertSessionHasErrors(['name', 'email']);
        $this->assertSame('Original', $user->fresh()->name);
        $this->assertDatabaseMissing('audit_logs', ['action' => 'user.updated']);
    }

    public function test_administrator_can_delete_a_common_user_and_preserves_audit(): void
    {
        $admin = User::factory()->administrator()->create();
        $user = User::factory()->create();
        $event = AuditLog::factory()->create(['user_id' => $user->id]);
        $this->actingAs($admin)->delete('/admin/usuarios/'.$user->id)->assertRedirect(route('users.index'));
        $this->assertModelMissing($user);
        $this->assertModelExists($event);
        $this->assertNull($event->fresh()->user_id);
        $this->assertDatabaseHas('audit_logs', ['action' => 'user.deleted', 'user_id' => $admin->id]);
    }

    public function test_administrator_accounts_cannot_be_deleted(): void
    {
        $admin = User::factory()->administrator()->create();
        $this->actingAs($admin)->delete('/admin/usuarios/'.$admin->id)->assertSessionHasErrors('user');
        $this->assertModelExists($admin);
    }

    public function test_user_content_is_escaped(): void
    {
        $user = User::factory()->create(['name' => '<script>alert(1)</script>']);
        $this->actingAs($user)->get('/perfil')->assertSee('&lt;script&gt;alert(1)&lt;/script&gt;', false)->assertDontSee('<script>alert(1)</script>', false);
    }

    public function test_logout_ends_access_and_is_logged(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user)->post('/sair')->assertRedirect(route('login'));
        $this->assertGuest();
        $this->get('/perfil')->assertRedirect(route('login'));
        $this->assertDatabaseHas('audit_logs', ['action' => 'logout', 'user_id' => $user->id]);
    }

    public function test_public_pages_render(): void
    {
        $this->get('/cadastro')->assertOk()->assertSee('Crie sua conta');
        $this->get('/login')->assertOk()->assertSee('Acesse sua conta');
    }

    public function test_console_creates_hashed_administrator_without_public_role_selection(): void
    {
        $this->artisan('app:create-admin', ['name' => 'Administrador', 'email' => 'admin@example.com'])->expectsQuestion('Senha (8 a 72 caracteres)', 'SenhaSegura123')->expectsOutput('Administrador criado com sucesso.')->assertSuccessful();
        $user = User::where('email', 'admin@example.com')->firstOrFail();
        $this->assertSame('admin', $user->role);
        $this->assertTrue(Hash::check('SenhaSegura123', $user->password));
        $this->assertDatabaseHas('audit_logs', ['action' => 'admin.created', 'user_id' => $user->id]);
    }
}
