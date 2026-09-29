    .syntax unified
    .arm

    .section .vetores, "ax"
    .global _vetores
_vetores:
    ldr pc, v_reset
    ldr pc, v_parado
    ldr pc, v_parado
    ldr pc, v_parado
    ldr pc, v_parado
    .word 0
    ldr pc, [pc, #-0xFF0]
    ldr pc, v_parado

v_reset:  .word reset
v_parado: .word parado

    .text
    .global reset
reset:
    ldr r0, =_pilha_topo
    msr cpsr_c, #0xD2
    mov sp, r0
    sub r0, r0, #512
    msr cpsr_c, #0xD3
    mov sp, r0

    ldr r0, =_dados_carga
    ldr r1, =_dados_ini
    ldr r2, =_dados_fim
copia:
    cmp r1, r2
    ldrlo r3, [r0], #4
    strlo r3, [r1], #4
    blo copia

    ldr r1, =_bss_ini
    ldr r2, =_bss_fim
    mov r3, #0
zera:
    cmp r1, r2
    strlo r3, [r1], #4
    blo zera

    msr cpsr_c, #0x53
    bl main

parado:
    b parado
