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

modal_alert.container.style.backgroundColor = ""
modal_alert.container.style.color = ""
modal_alert.container.classList.add('console-color')

const RERUN_MODAL = new Modal(document.getElementById('rerun-popup'),
{
    width: '35rem',
    height: '20rem',
    displayStyle: 'flex',
})


function rerun_trigger(job_name, jobid) {
    RERUN_MODAL.open().then(popup=>{
        let job_name_prompt = popup.querySelector("#popup-rerun-prompt")
        job_name_prompt.focus()

        popup.querySelector("#popup-rerun-btn").onclick = ()=>{ // assign rerun button action
            let updated_kwargs = {}
            let updated_types = {}
            for (let kwarg of popup.querySelectorAll(".rerun-kwarg")) {
                let input_elem = kwarg.querySelector("input")
                let new_val
                if (input_elem.type === 'checkbox') { // boolean
                    new_val = input_elem.checked ? 'true' : 'false'
                } else {
                    new_val = input_elem.value
                }
                let orig_value = kwarg.getAttribute('data-value')
                if (orig_value !== new_val) {
                    console.log("updated", orig_value, new_val)
                    updated_kwargs[kwarg.getAttribute('data-key')] = new_val
                    updated_types[kwarg.getAttribute('data-key')] = kwarg.getAttribute('data-type')
                }
            }

            let job_name_text = job_name_prompt.value
            console.log(job_name, jobid, updated_kwargs, job_name_text)
            if (job_name_text == job_name) {
                send_rerun_request(jobid, updated_kwargs, updated_types)
            } else {
                modal_alert.open("Rerun aborted")
            }
            RERUN_MODAL.close()
        }
    })
}


function send_rerun_request(jobid, kwargs, types) {
    const payload = {jobid, kwargs, types, api_token: API_TOKEN}
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
