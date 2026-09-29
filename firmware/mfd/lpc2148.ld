ENTRY(_vetores)

MEMORY
{
    FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 0x7C000
    RAM (rwx) : ORIGIN = 0x40000000, LENGTH = 0x7FE0
}

SECTIONS
{
    .text :
    {
        KEEP(*(.vetores))
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
    } > FLASH

    .data :
    {
        . = ALIGN(4);
        _dados_ini = .;
        *(.data*)
        . = ALIGN(4);
        _dados_fim = .;
    } > RAM AT > FLASH
    _dados_carga = LOADADDR(.data);

    .bss (NOLOAD) :
    {
        . = ALIGN(4);
        _bss_ini = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _bss_fim = .;
    } > RAM

    _pilha_topo = ORIGIN(RAM) + LENGTH(RAM);

    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) }
}
