Number.prototype.pad = function(size) {
    let s = String(this);
    while (s.length < (size || 2)) {s = "0" + s;}
    return s;
}

function countdown_str(seconds) {
    let hours = Math.floor(seconds / (60*60))
    seconds -= hours * (60*60)
    let minutes = Math.floor(seconds / 60)
    seconds -= minutes * 60
    return `${hours.pad()}:${minutes.pad()}:${Math.floor(seconds).pad()}`
}
function rerun_trigger(job_name, jobid) {
    const input_txt = prompt("Please type in the job name to confirm rerun", "");
    console.log(jobid)
    const payload = {jobid, api_token: API_TOKEN}
    if (input_txt===job_name) {
        fetch('./rerun', {method: 'POST', body: JSON.stringify(payload)}).then(resp => {
            return resp.json();
        }).then(j=>{
            if (j.success)
                window.location.reload()
            else if (j.error)
                throw Error(j.error)
            else
                throw Error("Rerun failed")
        }).catch(e=>alert(e))
    } else {
        alert("Rerun aborted")
    }
}
function enable_disable(job_name, jobid, disable) {
    const prompt_txt = "Please type in the job name to confirm " + ((disable) ? "disable": "enable")
    const input_txt = prompt(prompt_txt, "");
    console.log(jobid)
    const payload = {jobid, disable, api_token: API_TOKEN}
    if (input_txt===job_name) {
        fetch('./enable_disable', {method: 'POST', body: JSON.stringify(payload)}).then(resp => {
            return resp.json();
        }).then(j=>{
            if (j.success)
                window.location.reload()
            else if (j.error)
                throw Error(j.error)
            else
                throw Error("Action failed")
        }).catch(e=>alert(e))
    } else {
        alert("Action aborted")
    }
}
window.addEventListener('load', (event) => {
    //scroll to bottom
    document.getElementsByClassName("log_table")[0].querySelectorAll("div").forEach(d=>d.scrollTo(0,d.scrollHeight))
    if (RUNNING) {
        setTimeout(()=>location.reload(), TASKPAGE_REFRESH * 1000)
    } else if ( isNaN(NEXT_RUN) ) { // if not number
        document.getElementById("next-run-in").innerHTML = NEXT_RUN
    } else {
        const timer = setInterval(()=>{
            let ttr = (NEXT_RUN * 1000)-Date.now()
            if (ttr<=0) {
                clearInterval(timer)
                setTimeout(()=>location.reload(), 1000) // small timeout to avoid too many reloads
            } else {
                document.getElementById("next-run-in").innerHTML = countdown_str(ttr/1000)
            }
        }, 1000)
    }
    //highlight error line
    if (ERR_LINE>=0) {
        hljs.initHighlightLinesOnLoad([
            [{start: ERR_LINE, end: ERR_LINE, color: 'rgba(255, 0, 0, 0.4)'}], // Highlight some lines in the first code block.
        ]);
    }
});
