-- Row-level security por fazenda (RNF07). Rode depois de criar as tabelas
-- (`ipeia criar-banco`) com um usuário dono das tabelas:
--   psql "$DATABASE_URL" -f sql/rls_postgres.sql
--
-- A aplicação deve conectar com um papel SEM o atributo BYPASSRLS e que não seja
-- dono das tabelas (ex.: ipeia_app). O dono (usado no cadastro e nas migrações)
-- não passa pelo RLS, porque não usamos FORCE ROW LEVEL SECURITY. A cada transação, o código chama
-- set_config('app.fazenda_id', <id>, true) (ver banco/sessao.py:definir_fazenda).
--
-- A tabela `usuarios` fica fora do RLS porque é por ela que o webhook descobre
-- a fazenda de um número de WhatsApp. Restrinja o acesso a ela por GRANT.

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['tanques', 'apelidos_tanque', 'lotes', 'pendencias',
                             'lancamentos', 'consultas_tecnicas']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS isolamento_fazenda ON %I', t);
        EXECUTE format(
            'CREATE POLICY isolamento_fazenda ON %I USING (fazenda_id = current_setting(''app.fazenda_id'', true)) '
            'WITH CHECK (fazenda_id = current_setting(''app.fazenda_id'', true))', t);
    END LOOP;
END $$;

-- Mensagens de números ainda não cadastrados ficam sem fazenda.
ALTER TABLE mensagens_recebidas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS isolamento_fazenda ON mensagens_recebidas;
CREATE POLICY isolamento_fazenda ON mensagens_recebidas
    USING (fazenda_id IS NULL OR fazenda_id = current_setting('app.fazenda_id', true))
    WITH CHECK (fazenda_id IS NULL OR fazenda_id = current_setting('app.fazenda_id', true));

-- A tabela de fazendas só mostra a fazenda corrente.
ALTER TABLE fazendas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS isolamento_fazenda ON fazendas;
CREATE POLICY isolamento_fazenda ON fazendas
    USING (id = current_setting('app.fazenda_id', true));
