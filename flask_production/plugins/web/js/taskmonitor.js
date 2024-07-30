const table = document.getElementById("all-jobs")
const filter_box = document.getElementById("filter-box");
new Tablesort(table);
const tf = new TableFilter(table, filter_box)

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
})
