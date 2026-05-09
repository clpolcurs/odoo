/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FileUploader } from "@web/views/fields/file_handler";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { url } from "@web/core/utils/urls";
import { isBinarySize } from "@web/core/utils/binary";
import { Component } from "@odoo/owl";
import {
    onWillUpdateProps,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";

const { DateTime } = luxon;

function audioCacheKey(value) {
    if (value instanceof DateTime) {
        return value.ts;
    }
    return "";
}

export class AudioField extends Component {
    static template = "audio_field_is.AudioField";
    static components = { FileUploader };
    static props = {
        ...standardFieldProps,
        acceptedFileExtensions: { type: String, optional: true },
    };
    static defaultProps = {
        acceptedFileExtensions: "audio/*",
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ isValid: true });
        this.audioRef = useRef("AudioFieldComponent");
        this.rawCacheKey = Date.now();

        onWillUnmount(() => this._willUnmount());

        onWillUpdateProps((nextProps) => {
            const { record } = this.props;
            const { record: nextRecord } = nextProps;
            const nextValue = nextRecord.data[this.props.name];

            if (record.resId !== nextRecord.resId || nextRecord.mode === "readonly") {
                this.rawCacheKey = nextRecord.data.__last_update;
            }

            if (this.audioRef.el && nextValue) {
                const audioEl = this.audioRef.el.querySelector("audio");
                if (audioEl) {
                    audioEl.pause();
                    const source = audioEl.querySelector("source");
                    if (source) {
                        source.remove();
                    }
                    const newSource = document.createElement("source");
                    newSource.src = this.getUrl(nextRecord.resId);
                    audioEl.appendChild(newSource);
                    audioEl.load();
                }
            }
        });
    }

    get fieldValue() {
        return this.props.record.data[this.props.name];
    }

    getUrl(recId) {
        const value = this.fieldValue;
        if (this.state.isValid && value) {
            if (isBinarySize(value)) {
                if (!this.rawCacheKey) {
                    this.rawCacheKey = this.props.record.data.__last_update;
                }
                return url("/web/content", {
                    model: this.props.record.resModel,
                    id: recId || this.props.record.resId,
                    field: this.props.name,
                    unique: audioCacheKey(this.rawCacheKey),
                });
            } else {
                return `data:audio/mpeg;base64,${value}`;
            }
        }
        return "";
    }

    _willUnmount() {
        const value = this.fieldValue;
        if (this.audioRef.el && value) {
            const audioEl = this.audioRef.el.querySelector("audio");
            if (audioEl) {
                audioEl.pause();
            }
        }
    }

    onFileRemove() {
        this.state.isValid = true;
        if (this.props.record && this.props.name) {
            try {
                this.props.record.update({ [this.props.name]: false });
            } catch (error) {
                console.error("Failed to remove audio from record:", error);
            }
        }
    }

    async onFileUploaded(info) {
        console.log("Upload triggered, received info:", info);
        this.state.isValid = true;
        this.rawCacheKey = null;
        try {
            await this.props.record.update({ [this.props.name]: info.data });
        } catch (error) {
            console.error("Failed to update record with uploaded audio:", error);
            this.notification.add("Upload failed", { type: "danger" });
        }
    }

    onLoadFailed() {
        this.state.isValid = false;
        this.notification.add(this.env._t("Could not load the selected audio file."), {
            type: "danger",
        });
    }
}

export const audioField = {
    component: AudioField,
    supportedTypes: ["binary"],
    extractProps: ({ options }) => ({
        acceptedFileExtensions: options.accepted_file_extensions,
    }),
};

registry.category("fields").add("audio_player", audioField);
