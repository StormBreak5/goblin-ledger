"""CU11 – pipeline do modelo preditivo global (porte de `estudos/lstm/`).

Roda só no serviço `modelo` (imagem com pandas e TensorFlow). A API só registra o pedido (src/services/treinamento_service.py)
e importa apenas `configuracao` (sem pandas), para recalcular a RN02 e a RN27 com os mesmos limites (CU05-C1-FA2).
"""
