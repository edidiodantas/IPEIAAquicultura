# Especificação revisada: sistema de gestão aquícola (v2)

2 de novembro de 2026 · Edídio

## Resumo das correções

A especificação está bem orientada, mas tem três pontos que não funcionam como escritos: o serverless puro conflita com o KV-Cache, o acervo inteiro não cabe na janela de um modelo 7B, e o WhatsApp não fornece o horário de envio no celular. As demais mudanças fecham lacunas, como o roteador de intenção, que aparecia na introdução mas não tinha requisito.

| Requisito | Problema | Correção |
| --- | --- | --- |
| RNF04 x RNF05 | Serverless que escala a zero descarta o KV-Cache, e cada pergunta reprocessa o acervo inteiro. | Manter uma instância aquecida no horário de uso (por exemplo, das 5h às 20h) ou usar um provedor com cache de prefixo. A meta de custo passa a ser mensal, com uma parte fixa. |
| RF06 / RNF05 | Um único manual técnico pode ter de 60 mil a 200 mil tokens (estimativa). A janela do modelo base é de 32 mil tokens, ou 128 mil com extensão. | Dividir o acervo em blocos temáticos (espécie, sanidade, qualidade da água, nutrição). O roteador escolhe o bloco, e só esse bloco fica em cache. |
| RNF06 | O webhook do WhatsApp informa a hora em que o servidor recebeu a mensagem, não a hora em que o produtor a gravou sem sinal. | Gravar três horários: o do manejo dito no áudio ("tratei às 7h"), o do recebimento pelo WhatsApp e o do processamento. |
| RNF02 | Temperatura 0 reduz a variação, mas não garante que a resposta seja factual. | Manter a temperatura 0 e exigir que o modelo cite o trecho do manual. O código confere se o trecho existe no acervo. |
| RNF03 | Um modelo 7B não obedece a uma instrução de recusa de forma confiável. | Se a citação não for encontrada no acervo, o código substitui a resposta pela frase padrão. |
| RF02 x RF05 | A ordem não estava definida, e o produtor poderia confirmar um registro inválido. | Primeiro valida, depois pede a confirmação. Um registro sem confirmação expira em 24 horas. |
| RF07 | Se o próprio modelo escrever o aviso, ele pode omiti-lo. | O código anexa o aviso. |
| Roteamento | Citado na introdução, mas sem requisito próprio. | Novo RF08. |

A "Camada Tripla de Proteção" fica definida assim: (1) validação zootécnica por código, (2) confirmação humana no WhatsApp e (3) barreira de citação com aviso legal no módulo técnico. Os números de tokens e de janela de contexto são aproximados e devem ser medidos com os manuais reais.

## Requisitos Funcionais (RF)

Os RF01 a RF07 mantêm a numeração original. Os RF08 a RF10 são novos.

### 1. Interface e captura de voz (WhatsApp)

**RF01 – Transcrição assíncrona de áudio.** O sistema captura áudios e textos do WhatsApp e transcreve os áudios com Whisper (por exemplo, faster-whisper). Um vocabulário de jargões da aquicultura vai no prompt inicial do Whisper: alevino, arraçoamento, biometria, tilápia, tambaqui, despesca. Se a confiança da transcrição for baixa, o sistema pede ao produtor que repita ou digite.

**RF02 – Confirmação ativa de lançamento.** Depois da validação do RF05, o sistema responde com um resumo do registro, mostra o que entendeu do áudio e exibe os botões \[Confirmar\] / \[Corrigir\] / \[Cancelar\]. Somente o Confirmar grava o registro como definitivo. Um registro pendente expira em 24 horas, que é também a janela em que o WhatsApp permite mensagens livres.

### 2. Operação e comando (extração estruturada)

**RF03 – Extração de entidades operacionais.** O Amadeus-Verbo extrai, em JSON validado por esquema, os seguintes campos: tanque (ID ou apelido), lote, quantidade e unidade de ração (kg, sacos, "meio saco"), fase ou tipo da ração, mortalidade (número de peixes) e data e hora do manejo, quando ditas. Um áudio pode conter vários tanques, e o resultado é uma lista. O código converte todas as unidades para kg usando o peso do saco cadastrado.

**RF04 – Dicionário dinâmico de apelidos.** O sistema traduz apelidos ("tanque da entrada") para IDs da propriedade com busca aproximada. Se houver dois candidatos, o sistema pergunta qual é. Se o apelido for desconhecido, oferece cadastrá-lo.

**RF05 – Validação de limites zootécnicos por código.** Regras em Pydantic verificam os dados contra limites parametrizados por espécie, fase e biomassa do lote. Os limites vêm dos manuais e do técnico responsável, não do modelo. Há dois níveis: alerta (fora do usual, o produtor pode confirmar com justificativa) e bloqueio (fisicamente impossível, como mais peixes mortos do que o lote tem).

### 3. Assistência técnica (CAG)

**RF06 – Consulta ao acervo estático.** O sistema responde dúvidas técnicas usando apenas o bloco temático do acervo escolhido pelo roteador. Cada resposta cita o manual, a página e o trecho usado.

**RF07 – Aviso obrigatório.** O código anexa, a toda resposta técnica, a orientação de validar a recomendação com um Engenheiro de Pesca ou Médico Veterinário antes de intervenções sanitárias. O modelo não redige o aviso.

### 4. Novos requisitos

**RF08 – Roteamento de intenção.** Cada mensagem é classificada em manejo, consulta técnica, correção ou outro. O modelo responde apenas com o rótulo, em saída restrita, e o código despacha para o fluxo certo. Uma mensagem que mistura manejo e dúvida é dividida em duas. Se a classificação for incerta, o sistema pergunta.

**RF09 – Cadastro da propriedade.** O sistema mantém o cadastro de tanques (área e volume), apelidos, lotes (espécie, quantidade, peso médio), peso do saco de ração e usuários autorizados (números de WhatsApp) de cada fazenda. O cadastro é feito por um painel web simples ou pelo próprio WhatsApp.

**RF10 – Correção e estorno.** O produtor pode corrigir ou estornar um lançamento já confirmado ("o de ontem no tanque 2 foi 20 kg, não 30"). O registro original nunca é apagado. O sistema grava um registro de estorno ligado a ele.

## Requisitos Não Funcionais (RNF)

Os RNF01 a RNF07 foram reescritos para serem verificáveis. Os RNF08 a RNF11 são novos.

### 1. Motor de linguagem

**RNF01 – Motor nativo.** O motor padrão é o Amadeus-Verbo-MI-7B-Instruct. O 14B é usado se o 7B não atingir a meta de acurácia. Antes de fixar o modelo, ele é testado com um conjunto de pelo menos 200 áudios reais de produtores, com meta de 95% de campos extraídos corretamente. A licença de uso comercial do modelo é conferida antes do lançamento.

**RNF02 – Determinismo no módulo técnico.** Temperatura 0.0 e semente fixa no módulo técnico e na extração. Essa configuração reduz a variação entre respostas, mas não substitui a verificação do RNF03.

**RNF03 – Barreira de alucinação.** O modelo deve devolver a resposta junto com o trecho literal do manual que a sustenta. O código procura esse trecho no acervo. Se não o encontrar, descarta a resposta e envia exatamente: "Não encontrei essa informação nos manuais técnicos de segurança cadastrados."

### 2. Infraestrutura, desempenho e custos

**RNF04 – Custo controlado.** O backend (webhook, filas, banco) é serverless. A inferência roda em GPU com cobrança por segundo, com uma instância aquecida nos horários de manejo e escala a zero no resto do dia. A meta passa a ser um teto mensal em reais para 1.000 requisições por dia, a ser definido no passo 2 do plano com cotação real dos provedores.

**RNF05 – Reaproveitamento de KV-Cache.** O servidor de inferência (vLLM com cache automático de prefixo) mantém em cache cada bloco temático do acervo. Cada bloco deve caber em até metade da janela de contexto efetiva do modelo, e o restante fica para a pergunta e a resposta. A meta é acertar o cache em 90% das perguntas feitas com a instância aquecida.

**RNF06 – Resiliência à latência rural.** O processamento é assíncrono, por fila. Cada registro grava a hora do manejo (dita pelo produtor ou, na falta dela, a do WhatsApp), a hora de recebimento pelo WhatsApp e a hora de processamento. Mensagens repetidas pelo WhatsApp são descartadas pelo ID da mensagem, para não gerar lançamento em dobro.

### 3. Segurança e governança de dados

**RNF07 – Isolamento e LGPD.** Os dados ficam em PostgreSQL com criptografia em repouso e em trânsito. Cada fazenda é isolada por segurança em nível de linha (row-level security). Os contratos com todos os provedores que veem os dados (WhatsApp, transcrição, inferência) devem proibir o uso para treinamento. Os áudios são apagados depois de 90 dias, e o produtor dá consentimento no primeiro contato.

### 4. Novos requisitos

**RNF08 – Tempo de resposta.** O produtor recebe a confirmação de um manejo em até 30 segundos e a resposta técnica em até 60 segundos, com a instância aquecida. Fora do horário aquecido, o sistema avisa logo que recebeu e responde em até 3 minutos.

**RNF09 – Trilha de auditoria.** Cada lançamento guarda o áudio (dentro do prazo de retenção), a transcrição, o JSON extraído, o resultado da validação e quem confirmou e quando.

**RNF10 – Versionamento do acervo.** Cada manual tem versão e data de homologação. Toda resposta técnica registra a versão do acervo usada.

**RNF11 – Testes de regressão.** Um conjunto fixo de áudios e perguntas roda a cada troca de modelo, prompt ou acervo. A troca só vai para produção se a acurácia não cair.

## Decisões em aberto

Estas escolhas mudam o custo ou o escopo. Por isso ficam com você antes do passo 2 (arquitetura).

- [ ] Qual o teto de custo mensal aceitável em reais, incluindo a GPU aquecida nos horários de manejo?
- [ ] Quais espécies o MVP atende (só tilápia ou também tambaqui, camarão)? Essa escolha define os blocos do acervo e as tabelas de limites.
- [ ] Quem fornece e assina os limites zootécnicos do RF05: um Engenheiro de Pesca parceiro ou somente os manuais?
- [ ] Quais manuais entram na primeira versão do acervo, e eles têm licença de uso (a Embrapa publica muitos em acesso aberto, mas cada um deve ser conferido)?
- [ ] O produtor também poderá consultar o histórico pelo WhatsApp ("quanto de ração gastei no tanque 3 esta semana?")? Isso seria um RF11 novo.
- [ ] O cadastro inicial da fazenda (RF09) será feito por um painel web ou só pelo WhatsApp?
