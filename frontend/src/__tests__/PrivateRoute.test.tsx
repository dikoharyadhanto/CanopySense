import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PrivateRoute from '../components/PrivateRoute';

function TestProtected() {
  return <div>Protected Content</div>;
}

function TestLogin() {
  return <div>Login Page</div>;
}

function renderWithRouter(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<TestLogin />} />
        <Route element={<PrivateRoute />}>
          <Route path="/dashboard" element={<TestProtected />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('PrivateRoute', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('redirects to /login when no token is stored', () => {
    renderWithRouter('/dashboard');
    expect(screen.getByText('Login Page')).toBeDefined();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('renders protected content when a token is stored', () => {
    localStorage.setItem('token', 'header.eyJzdWIiOiJ1c2VyIn0.sig');
    renderWithRouter('/dashboard');
    expect(screen.getByText('Protected Content')).toBeDefined();
    expect(screen.queryByText('Login Page')).toBeNull();
  });
});
