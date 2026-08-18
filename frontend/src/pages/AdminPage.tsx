import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

type AdminUser = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
};

type CreateUserBody = {
  email: string;
  password: string;
  role: string;
};

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('user');
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: users, isLoading, isError, error } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => (await apiClient.get<AdminUser[]>('/admin/users')).data,
  });

  const createMutation = useMutation({
    mutationFn: async (body: CreateUserBody) =>
      (await apiClient.post('/admin/users', body)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setShowCreate(false);
      setNewEmail('');
      setNewPassword('');
      setNewRole('user');
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err?.response?.data?.detail ?? 'Error al crear usuario');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async (userId: number) =>
      (await apiClient.patch(`/admin/users/${userId}`, { is_active: " + fval + " })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err?.response?.data?.detail ?? 'Error al desactivar usuario');
    },
  });

  const resetMutation = useMutation({
    mutationFn: async ({ userId, new_password }: { userId: number; new_password: string }) =>
      (await apiClient.post(`/admin/users/${userId}/reset-password`, { new_password })).data,
    onSuccess: () => {
      setResetUserId(null);
      setResetPassword('');
      setActionError(null);
    },
    onError: (err: any) => {
      setActionError(err?.response?.data?.detail ?? 'Error al resetear password');
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({ email: newEmail, password: newPassword, role: newRole });
  };

  const handleReset = (e: React.FormEvent) => {
    e.preventDefault();
    if (resetUserId !== null) {
      resetMutation.mutate({ userId: resetUserId, new_password: resetPassword });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Administración de Usuarios</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreate(!showCreate)}
          data-testid="toggle-create"
        >
          {showCreate ? 'Cancelar' : 'Nuevo usuario'}
        </button>
      </div>

      {actionError && (
        <div className="alert alert-error" data-testid="action-error">
          {actionError}
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="card bg-base-200" data-testid="create-form">
          <div className="card-body space-y-3">
            <h2 className="card-title text-lg">Crear usuario</h2>
            <input
              type="email"
              placeholder="Email"
              className="input input-bordered w-full"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              required
              data-testid="new-email"
            />
            <input
              type="password"
              placeholder="Password (mín. 8 caracteres)"
              className="input input-bordered w-full"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
              data-testid="new-password"
            />
            <select
              className="select select-bordered w-full"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              data-testid="new-role"
            >
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createMutation.isPending}
              data-testid="submit-create"
            >
              {createMutation.isPending ? 'Creando…' : 'Crear'}
            </button>
          </div>
        </form>
      )}

      {isLoading && <div className="alert">Cargando usuarios…</div>}
      {isError && (
        <div className="alert alert-error">
          Error al cargar usuarios: {(error as any)?.message ?? 'desconocido'}
        </div>
      )}

      {users && (
        <div className="overflow-x-auto">
          <table className="table table-zebra" data-testid="users-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Rol</th>
                <th>Activo</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} data-testid={`user-row-${u.id}`}>
                  <td>{u.email}</td>
                  <td>
                    <span className={`badge ${u.role === 'admin' ? 'badge-primary' : 'badge-ghost'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'badge-success' : 'badge-error'}`}>
                      {u.is_active ? 'sí' : 'no'}
                    </span>
                  </td>
                  <td className="space-x-2">
                    {u.is_active && (
                      <button
                        className="btn btn-sm btn-warning"
                        onClick={() => deactivateMutation.mutate(u.id)}
                        disabled={deactivateMutation.isPending}
                        data-testid={`deactivate-${u.id}`}
                      >
                        Desactivar
                      </button>
                    )}
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => {
                        setResetUserId(u.id);
                        setResetPassword('');
                      }}
                      data-testid={`reset-${u.id}`}
                    >
                      Reset password
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {resetUserId !== null && (
        <form onSubmit={handleReset} className="card bg-base-200" data-testid="reset-form">
          <div className="card-body space-y-3">
            <h2 className="card-title text-lg">Reset password para usuario #{resetUserId}</h2>
            <input
              type="password"
              placeholder="Nuevo password (mín. 8 caracteres)"
              className="input input-bordered w-full"
              value={resetPassword}
              onChange={(e) => setResetPassword(e.target.value)}
              minLength={8}
              required
              data-testid="reset-password-input"
            />
            <div className="flex gap-2">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={resetMutation.isPending}
                data-testid="submit-reset"
              >
                {resetMutation.isPending ? 'Reseteando…' : 'Resetear'}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setResetUserId(null);
                  setResetPassword('');
                }}
              >
                Cancelar
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
