#!/bin/bash
unknown_params_action=set
. $DLBS_ROOT/scripts/parse_options.sh || exit 1;    # Parse command line options
. $DLBS_ROOT/scripts/utils.sh
loginfo "$0 $*" >> ${exp_log_file}                  # Log command line arguments for debugging purposes
# The simulation mode: just print out what is about to be launched
if [ "$exp_status" = "simulate" ]; then
    echo "${caffe2_env} ${runtime_launcher} python ${caffe2_bench_path}/caffe2_benchmarks/benchmarks.py ${caffe2_args}"
    exit 0
fi
# Check batch is small enough for this experiment
__batch_file__="$(dirname ${exp_log_file})/${exp_framework}_${exp_device_type}_${exp_model}.batch"
is_batch_good "${__batch_file__}" "${exp_replica_batch}" || {
  report_and_exit "skipped" "The replica batch size (${exp_replica_batch}) is too large for given SW/HW configuration." "${exp_log_file}";
}
# This script is to be executed inside docker container or on a host machine.
# Thus, the environment must be initialized inside this scrip lazily.
[ -z "${runtime_launcher}" ] && runtime_launcher=":;"
script="\
    export ${caffe2_env};\
    echo -e \"__results.start_time__= \x22\$(date +%Y-%m-%d:%H:%M:%S:%3N)\x22\";\
    ${runtime_launcher} python ${caffe2_bench_path}/caffe2_benchmarks/benchmarks.py ${caffe2_args} &\
    proc_pid=\$!;\
    [ \"${monitor_frequency}\" != \"0\" ] && echo -e \"\${proc_pid}\" > ${monitor_backend_pid_folder}/proc.pid;\
    wait \${proc_pid};\
    echo -e \"__results.end_time__= \x22\$(date +%Y-%m-%d:%H:%M:%S:%3N)\x22\";\
    echo -e \"__results.proc_pid__= \${proc_pid}\";\
"
if [ "${exp_docker}" = "true" ]; then
    assert_docker_img_exists ${exp_docker_image}
    ${exp_docker_launcher} run ${caffe2_docker_args} /bin/bash -c "eval $script" >> ${exp_log_file} 2>&1
else
    eval $script >> ${exp_log_file} 2>&1
fi

if caffe2_error ${exp_log_file}; then
    logwarn "error in \"${exp_log_file}\" with effective batch ${exp_effective_batch} (replica batch ${exp_replica_batch})";
    update_error_file "${__batch_file__}" "${exp_replica_batch}";
fi
