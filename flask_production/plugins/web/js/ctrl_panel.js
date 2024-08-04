window.addEventListener('load', (event) => {
    const timer = setInterval(()=>{
        if (COUNT_DOWN > 0) {
            COUNT_DOWN --
            document.getElementById('refresh-msg').innerText = COUNT_DOWN
        } else {
            clearInterval(timer)
            location.reload()
        }
    }, 1000)
    document.querySelectorAll('.monitor-block:not(.no-page)').forEach(block=>{
        block.addEventListener('click', ()=>{
            window.location.href=block.getAttribute("data-url")
        })
    })
});
